"""Offline rehearsal: feed the real 2023-2026 listings to the paper bot, hour by hour, through a
fake exchange built from the archive, and compare its bookkeeping with the backtest.

    python -m prop.live.rehearsal
"""
from __future__ import annotations

import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from prop.live import listing_paper as lp
from prop.persistence.state_store import StateStore


class ArchiveApi:
    def __init__(self, listed: dict[str, pd.Timestamp], klines: dict[str, pd.DataFrame], funding: dict[str, pd.Series]):
        self.listed, self.klines, self.fund = listed, klines, funding
        self.now = pd.Timestamp("2023-01-01", tz="UTC")

    def spot_symbols(self) -> set[str]:
        return {"BTCUSDT"} | {s for s, t in self.listed.items() if t <= self.now}

    def perp_symbols(self) -> set[str]:
        return {s for s, k in self.klines.items() if len(k) and k.index[0] <= self.now}

    def hourly(self, perp: str, start: pd.Timestamp) -> pd.DataFrame:
        k = self.klines[perp]
        return k[(k.index >= start.floor("h")) & (k.index < self.now)][["open", "high", "low", "close"]]

    def funding(self, perp: str, start: pd.Timestamp, end: pd.Timestamp) -> float:
        f = self.fund.get(perp)
        return float(f[(f.index >= start) & (f.index <= end)].sum()) if f is not None and len(f) else 0.0


def main() -> None:
    from kenui_trader import vision as v
    from research.listings_short import load
    logging.basicConfig(level=logging.WARNING)
    ev = pd.read_csv("data/listings_events.csv", parse_dates=["listed"]).sort_values("listed")
    futs = set(v.symbols("futures/um"))
    with ThreadPoolExecutor(8) as ex:
        loaded = [x for x in ex.map(lambda r: load(r, futs), [r for _, r in ev.iterrows()]) if x]
    listed = dict(zip(ev["symbol"], ev["listed"]))
    klines = {s: k.astype(float) for s, k, _ in loaded}
    fund = {s: f["last_funding_rate"] for s, _, f in loaded if len(f)}
    api = ArchiveApi(listed, klines, fund)
    barrier, harvest = lp.policies()
    with tempfile.TemporaryDirectory() as tmp:
        bot = lp.ListingPaper(StateStore(Path(tmp) / "r.db"), api, barrier, harvest)
        hot = sorted({t.floor("h") + pd.Timedelta(hours=h) for t in listed.values() for h in range(-1, lp.WAIT_H + lp.HOLD_H + 3)})
        for now in hot:                      # only the hours in which something can happen
            api.now = now
            bot.step(now)
        closed = pd.DataFrame(bot.closed)
        a = bot.account
    print(f"{len(closed)} operacoes fechadas, {len(bot.skipped)} ignoradas")
    print(f"R medio {closed['r'].mean():+.3f} (com funding), sem funding {((closed['ret'] - closed['funding']) / lp.STOP).mean():+.3f}")
    back = pd.read_csv("prop/output/listing_short_trades.csv")
    m = closed.merge(back, left_on="symbol", right_on="symbol", suffixes=("", "_bt"))
    diff = (m["ret"] - m["funding"]) / lp.STOP - m["r_bt"]
    print(f"pares em comum com o backtest: {len(m)}; diferenca media de R {diff.mean():+.4f}, maxima {diff.abs().max():.3f}, "
          f"correlacao {np.corrcoef((m['ret'] - m['funding']) / lp.STOP, m['r_bt'])[0, 1]:.4f}")
    print(f"conta simulada na ordem real: {a.passed_p1} Fases 1 aprovadas, {a.funded} contas financiadas, {a.failed} reprovacoes, "
          f"saques US$ {a.payouts_usd:.0f}, risco medio {100 * closed['risk'].mean():.2f}%")
    for t, e in a.events:
        print("  ", t[:10], e)


if __name__ == "__main__":
    main()
