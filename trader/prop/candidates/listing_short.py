"""Candidate from the earlier research, replayed under prop-firm rules.

Rule (found in `research/listings_short.py`, t = 3.7 on 190 cases): short the perpetual of a coin
24 hours after its Binance spot listing, hold 7 days, stop 30% above the entry.
It needs a venue with perpetual futures, e.g. a crypto prop firm that trades exchange prices.

Run: python -m prop.candidates.listing_short    (downloads ~200 small histories the first time)
"""
from __future__ import annotations

import dataclasses
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from kenui_trader import vision as v
from prop.backtest import engine, metrics, montecarlo as mc
from prop.config.settings import SETTINGS, Instrument, RiskConfig
from prop.strategies.indicators import empty_signals
from research.listings_short import COST, load

WAIT_H, HOLD_H, STOP = 24, 7 * 24, 0.30


def build() -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], dict[str, Instrument]]:
    ev = pd.read_csv("data/listings_events.csv", parse_dates=["listed"])
    futs = set(v.symbols("futures/um"))
    with ThreadPoolExecutor(8) as ex:
        loaded = [x for x in ex.map(lambda r: load(r, futs), [r for _, r in ev.iterrows()]) if x]
    listed = dict(zip(ev["symbol"], ev["listed"]))
    bars, sigs, inst = {}, {}, {}
    for sym, k, _funding in loaded:
        t_in = listed[sym] + pd.Timedelta(hours=WAIT_H)
        if len(k) == 0 or k.index[0] > t_in:
            continue  # perpetual not trading yet at the entry time
        df = k.loc[t_in - pd.Timedelta(hours=1): t_in + pd.Timedelta(hours=HOLD_H + 2),
                   ["open", "high", "low", "close", "volume"]].astype(float)
        if len(df) < HOLD_H or df.index[1] != t_in:
            continue
        sg = empty_signals(df.index)
        sg.iloc[0, sg.columns.get_loc("side")] = -1
        sg["stop_dist"] = STOP * df["close"]
        sg["tp_dist"] = 0.95 * df["close"]   # effectively no target
        sg["max_bars"], sg["engine"] = HOLD_H, "listing_short"
        bars[sym], sigs[sym] = df, sg
        inst[sym] = Instrument(sym, sym, "futures", COST, 1.0, 0.0, False)
    return bars, sigs, inst


def main() -> None:
    pd.set_option("display.width", 250)
    bars, sigs, inst = build()
    print(f"{len(bars)} listagens com contrato perpetuo negociando 24h depois")
    rows, rolls = [], []
    for risk_pct in (0.005, 0.01, 0.02):
        for label, cfg in (("sem travas", RiskConfig.plain(risk_pct)),
                           ("trava diaria 3%", dataclasses.replace(RiskConfig.plain(risk_pct), daily_hard_stop=0.03))):
            res = engine.run(bars, sigs, cfg, SETTINGS.rules, inst)
            m = metrics.summarize(res, SETTINGS.rules, inst)
            m.pop("expect_vs_custo"), m.pop("mesa")
            rows.append({"risco_%": risk_pct * 100, "travas": label, **m})
            rolls.append({"risco_%": risk_pct * 100, "travas": label,
                          **mc.rolling_equity(res.equity, res.worst, res.day_start)})
            if risk_pct == 0.01 and label == "sem travas":
                t = res.trades
                by_year = t.groupby(t["entry_time"].dt.year)["r"].agg(["count", "mean"]).round(3)
                res.trades.to_csv("prop/output/listing_short_trades.csv", index=False)
    print("\nBacktest da conta inteira (2023 a 2026):")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nResultado medio por trade (em R) por ano:")
    print(by_year.to_string())
    print("\nDesafio de 2 fases iniciado em cada dia real (limite de 365 dias por fase):")
    out = pd.DataFrame(rolls)
    out.to_csv("prop/output/listing_short_desafio.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
