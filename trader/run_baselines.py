"""Step 1 report: rank volatile coins, download history, run baselines walk-forward.

Usage:
    python run_baselines.py                 # top 8 volatile coins, 5m candles, 180 days
    python run_baselines.py --symbols SOLUSDT DOGEUSDT --interval 15m --days 365
"""
from __future__ import annotations

import argparse

import pandas as pd

from kenui_trader import data
from kenui_trader.backtest import walk_forward
from kenui_trader.strategies import BASELINES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--interval", default="5m")
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--capital", type=float, default=60.0)
    a = ap.parse_args()

    symbols = a.symbols
    if not symbols:
        ranked = data.top_volatile(n=a.top * 3)
        print("Most volatile liquid USDT pairs right now (24h):\n", ranked.to_string(), "\n")
        hv = data.historical_volatility(list(ranked["symbol"]), "1h", 90)
        print("Realized volatility, last 90 days:\n", hv.to_string(), "\n")
        symbols = list(hv["symbol"])  # walk down the list until `top` coins have enough history

    rows, used = [], []
    for sym in symbols:
        if len(used) >= a.top:
            break
        df = data.load(sym, a.interval, a.days)
        print(f"{sym}: {len(df)} candles {df.index[0]} -> {df.index[-1]}")
        expected = a.days * pd.Timedelta(days=1) / pd.Timedelta(a.interval.replace("m", "min"))
        if len(df) < 0.8 * expected:
            print(f"  skipping {sym}: only {len(df)} of ~{int(expected)} candles (listed too recently)")
            continue
        used.append(sym)
        for name, (fn, g) in BASELINES.items():
            wf = walk_forward(df, fn, g, n_splits=4, capital=a.capital)
            if wf.empty:
                continue
            rows.append({
                "symbol": sym, "strategy": name,
                "oos_return_%_avg": round(wf["total_return_%"].mean(), 2),
                "oos_return_%_worst": round(wf["total_return_%"].min(), 2),
                "buy_hold_%_avg": round(wf["buy_and_hold_%"].mean(), 2),
                "oos_sharpe_avg": round(wf["sharpe"].mean(), 2),
                "max_dd_%_worst": round(wf["max_drawdown_%"].min(), 2),
                "trades": int(wf["trades"].sum()),
                "profit_factor_avg": round(wf["profit_factor"].replace(float("inf"), 0).mean(), 2),
                "splits_positive": f"{(wf['total_return_%'] > 0).sum()}/{len(wf)}",
            })
    rep = pd.DataFrame(rows).sort_values("oos_sharpe_avg", ascending=False)
    print("\nOut-of-sample results (only on data each strategy was NOT tuned on):")
    print(rep.to_string(index=False))
    rep.to_csv("data/baseline_report.csv", index=False)


if __name__ == "__main__":
    main()
