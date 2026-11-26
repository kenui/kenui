"""Approximate fee/loss check for Orca SOL/USDC (no free archive of pool state on Solana).

fees: DefiLlama daily fee APY of the pool (fees / TVL)
loss: r^2/8 from Binance 10-minute prices (same formula as on Base)
The two are put on the same footing with the pool's concentration factor
c = TVL-equivalent of the active liquidity / TVL, measured now from the Orca API.
The method is first validated on the Base pool, where the exact answer is known.
"""
import json
import warnings

import numpy as np
import pandas as pd
import requests

from .chain import DATA_DIR
from .clmm import unit_edge
from . import research

warnings.filterwarnings("ignore")


def klines(symbol, start, end, interval="5m"):
    rows, t = [], int(start.timestamp() * 1000)
    while t < int(end.timestamp() * 1000):
        k = requests.get("https://data-api.binance.vision/api/v3/klines",
                         params={"symbol": symbol, "interval": interval, "startTime": t, "limit": 1000}, timeout=30).json()
        if not k:
            break
        rows += [(r[0], float(r[4])) for r in k]
        t = k[-1][0] + 1
    s = pd.Series(dict(rows))
    s.index = pd.to_datetime(s.index, unit="ms", utc=True)
    return s


def main():
    # --- validation on Base (exact numbers known) ---
    df = research.load("uni_weth_usdc_005")
    u = unit_edge(df)
    ll = pd.read_csv(DATA_DIR / "llama_uni_weth_usdc_005.csv", index_col=0); ll.index = pd.to_datetime(ll.index, utc=True, format="ISO8601")
    day = u.resample("D").sum()
    tvl_equiv = (2 * df.liq * df.sqrt).resample("D").mean()
    ll.index = ll.index.floor("D")
    j = day.join(ll[["apyBase", "tvlUsd"]], how="inner").join(tvl_equiv.rename("eqv"))
    j["c"] = j.eqv / j.tvlUsd
    j["fee_proxy"] = j.apyBase / 36500 / j.c.iloc[-30:].median()   # constant c, as we must assume on Solana
    print("Base validation: concentration c quartiles", j.c.quantile([.25, .5, .75]).round(1).tolist(),
          "| last-30d c", round(j.c.iloc[-30:].median(), 1))
    print(f"  exact fee/loss {j.fee_n.sum() / j.loss_n.sum():.2f}  vs proxy fee/loss {j.fee_proxy.sum() / j.loss_n.sum():.2f}")

    # --- Orca SOL/USDC ---
    live = [json.loads(l) for l in open(DATA_DIR / "orca_sol_usdc_004_live.jsonl")]
    a = live[-1]
    L = int(a["liquidity"]) / 10 ** 7.5
    sq = int(a["sqrtPrice"]) / 2 ** 64 * 10 ** 1.5
    c = 2 * L * sq / float(a["tvlUsdc"])
    ll = pd.read_csv(DATA_DIR / "llama_orca_sol_usdc.csv", index_col=0); ll.index = pd.to_datetime(ll.index, utc=True, format="ISO8601")
    ll.index = ll.index.floor("D")
    ll = ll[ll.index >= "2025-11-21"]
    px = klines("SOLUSDT", ll.index[0], ll.index[-1] + pd.Timedelta(days=1)).iloc[::2]
    loss = (np.log(px).diff() ** 2 / 8).resample("D").sum()
    j = pd.DataFrame({"fee": ll.apyBase / 36500 / c, "loss": loss}).dropna()
    print(f"\nOrca SOL/USDC 0.04%: price now {sq * sq:.2f}, concentration c now {c:.1f}")
    print(f"  proxy fee/loss over {len(j)} days: {j.fee.sum() / j.loss.sum():.2f}"
          f"   (if c were 30% lower: {j.fee.sum() / j.loss.sum() / 0.7:.2f}; 30% higher: {j.fee.sum() / j.loss.sum() / 1.3:.2f})")
    m = j.resample("MS").sum()
    print("  monthly:", " ".join(f"{k:%m/%y}:{v:.2f}" for k, v in (m.fee / m.loss).items()))

    # --- exact, but only for the hours sampled live ---
    if len(live) > 3:
        f = 0.0
        l = 0.0
        for p, q in zip(live[:-1], live[1:]):
            s0 = int(p["sqrtPrice"]) / 2 ** 64
            s1 = int(q["sqrtPrice"]) / 2 ** 64
            fa = (int(q["feeGrowthGlobalA"]) - int(p["feeGrowthGlobalA"])) % 2 ** 128 / 2 ** 64
            fb = (int(q["feeGrowthGlobalB"]) - int(p["feeGrowthGlobalB"])) % 2 ** 128 / 2 ** 64
            f += (fb + fa * s0 * s0) / (2 * s0)
            l += (s1 - s0) ** 2 / s0 / (2 * s0)
        hrs = (live[-1]["ts"] - live[0]["ts"]) / 3600
        print(f"  live exact sample ({hrs:.1f} h): fees {f * 1e4:.3f} bp vs loss {l * 1e4:.3f} bp -> fee/loss {f / max(l, 1e-18):.2f}")


if __name__ == "__main__":
    main()
