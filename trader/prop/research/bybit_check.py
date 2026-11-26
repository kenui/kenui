"""Does the listing short survive on Bybit? (the venue used by crypto prop firms)

For every trade of the Binance backtest (prop/config/listing_trades_binance.csv) this asks
Bybit's public API whether a USDT perpetual of the same coin was already trading at the entry
time, and replays the same rule on Bybit's own hourly bars and funding: short at the entry hour,
stop 30% above, out after 7 days, taker fee and slippage on both sides.

Bybit blocks cloud servers in some countries, so run it from a home connection:
    python -m prop.research.bybit_check
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

API = "https://api.bybit.com"
SRC = Path(__file__).resolve().parent.parent / "config" / "listing_trades_binance.csv"
STOP, HOLD_H = 0.30, 7 * 24
COST = 2 * (0.00055 + 0.0010)              # taker fee + slippage, both sides, fraction of notional


def get(path: str, **params) -> dict:
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research"}), timeout=20) as r:
                out = json.loads(r.read())
            if out.get("retCode") == 0:
                return out["result"]
            if out.get("retCode") in (10001,):                 # unknown symbol
                return {}
        except Exception as err:                                # noqa: BLE001
            if attempt == 3:
                raise SystemExit(f"sem acesso a Bybit ({err}). Rode de uma conexao de casa.")
        time.sleep(1 + attempt)
    return {}


def names(symbol: str) -> list[str]:
    base = symbol.removesuffix("USDT")
    return [symbol, f"1000{base}USDT", f"10000{base}USDT", f"1000000{base}USDT"]


def replay(symbol: str, t_in: pd.Timestamp) -> dict | None:
    start = int(t_in.timestamp() * 1000)
    end = start + (HOLD_H + 1) * 3_600_000
    for name in names(symbol):
        res = get("/v5/market/kline", category="linear", symbol=name, interval="60", start=start, end=end, limit=200)
        rows = sorted(res.get("list", []), key=lambda x: int(x[0]))
        if rows and int(rows[0][0]) == start and len(rows) >= HOLD_H:
            break
    else:
        return None
    o, h, c = (np.array([float(x[i]) for x in rows[:HOLD_H]]) for i in (1, 2, 4))
    entry = o[0]
    hit = np.nonzero(h >= entry * (1 + STOP))[0]
    n = int(hit[0]) + 1 if len(hit) else HOLD_H
    exit_px = entry * (1 + STOP) if len(hit) else c[-1]
    fund = get("/v5/market/funding/history", category="linear", symbol=name, startTime=start, endTime=start + n * 3_600_000, limit=200)
    funding = sum(float(x["fundingRate"]) for x in fund.get("list", []))          # a short receives positive funding
    ret = (entry - exit_px) / entry - COST
    return {"bybit": name, "r_bybit": ret / STOP, "funding_r_bybit": funding / STOP, "stopped": bool(len(hit))}


def main() -> None:
    t = pd.read_csv(SRC, parse_dates=["entry_time"])
    print(f"hora da Bybit: {get('/v5/market/time').get('timeSecond')}  |  {len(t)} operacoes do teste na Binance", flush=True)
    rows = []
    for i, r in t.iterrows():
        out = replay(r["symbol"], r["entry_time"])
        rows.append({"symbol": r["symbol"], "entry_time": r["entry_time"], "r_binance": r["r"] + r["funding_r"], **(out or {})})
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(t)}", flush=True)
        time.sleep(0.12)
    d = pd.DataFrame(rows)
    ok = d.dropna(subset=["r_bybit"]).copy()
    ok["net_bybit"] = ok["r_bybit"] + ok["funding_r_bybit"]
    tstat = lambda x: float(x.mean() / x.std(ddof=1) * np.sqrt(len(x))) if len(x) > 2 else float("nan")   # noqa: E731
    print(f"\ncontrato na Bybit ja aberto na hora da entrada: {len(ok)} de {len(d)} ({100 * len(ok) / len(d):.0f}%)")
    print(f"resultado medio na Bybit (em R, com taxa, derrapagem e funding): {ok['net_bybit'].mean():+.3f}  t = {tstat(ok['net_bybit']):.2f}"
          f"  | sem funding {ok['r_bybit'].mean():+.3f}")
    print(f"as mesmas operacoes na Binance: {ok['r_binance'].mean():+.3f}  | todas as {len(d)} na Binance: {d['r_binance'].mean():+.3f}")
    print(f"sem contrato na Bybit, resultado que teriam na Binance: {d[d['r_bybit'].isna()]['r_binance'].mean():+.3f}")
    print(f"acertos {100 * (ok['net_bybit'] > 0).mean():.0f}%  | stops {100 * ok['stopped'].mean():.0f}%  | correlacao Bybit x Binance {ok['net_bybit'].corr(ok['r_binance']):.2f}")
    print("\npor ano (n, media em R na Bybit, media na Binance):")
    for y, g in ok.groupby(ok["entry_time"].dt.year):
        print(f"  {y}: {len(g):3d}  {g['net_bybit'].mean():+.3f}  {g['r_binance'].mean():+.3f}")
    print(f"\noperacoes por mes na Bybit: {len(ok) / max(1, (d['entry_time'].max() - d['entry_time'].min()).days / 30.4):.1f}")
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC.with_name("listing_trades_bybit.csv")
    d.to_csv(out, index=False)
    print(f"salvo em {out}")
    print("\nTABELA COMPLETA (csv):")
    print(ok[["symbol", "entry_time", "bybit", "r_bybit", "funding_r_bybit", "r_binance", "stopped"]].round(4).to_csv(index=False))


if __name__ == "__main__":
    main()
