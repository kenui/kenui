"""Concentrated-liquidity (Uniswap v3 style) position maths and a back-test.

Everything is expressed in token1 (USDC) per token0 (the volatile asset),
already adjusted for decimals. Fee income comes from the pool's real
feeGrowthGlobal counters, credited only while the price is inside the range.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

Q96 = 2 ** 96
Q128 = 2 ** 128


def prepare(raw: pd.DataFrame, dec0: int, dec1: int, block_ts) -> pd.DataFrame:
    """Turn raw snapshots into a float frame.

    price: token1 per token0 (human units)
    f0, f1: fees paid during the interval ENDING at this row, per unit of
            "human" liquidity (L_h = L_raw / 10**((dec0+dec1)/2)), in token0 / token1.
    """
    raw = raw[(raw.sqrtPriceX96 > 0) & (raw.liquidity > 0)]
    scale = 10 ** ((dec0 - dec1) / 2)  # sqrt_human = sqrt_raw * scale
    lscale = 10 ** ((dec0 + dec1) / 2)
    sq = np.array([int(v) / Q96 for v in raw.sqrtPriceX96], dtype=float) * scale
    fg0 = raw.fg0.tolist()
    fg1 = raw.fg1.tolist()
    # counters are uint256 that wrap by design
    d0 = [0.0] + [((b - a) % 2 ** 256) / Q128 for a, b in zip(fg0[:-1], fg0[1:])]
    d1 = [0.0] + [((b - a) % 2 ** 256) / Q128 for a, b in zip(fg1[:-1], fg1[1:])]
    df = pd.DataFrame({
        "ts": [block_ts(b) for b in raw.index],
        "sqrt": sq,
        "price": sq ** 2,
        "f0": np.array(d0) * lscale / 10 ** dec0,
        "f1": np.array(d1) * lscale / 10 ** dec1,
        "liq": np.array([int(v) for v in raw.liquidity], dtype=float) / lscale,
    })
    df["time"] = pd.to_datetime(df.ts, unit="s", utc=True)
    return df.set_index("time")


def unit_edge(df: pd.DataFrame) -> pd.DataFrame:
    """Per-interval fee income and rebalancing loss of ONE unit of in-range liquidity.

    For any in-range position: value change minus the change of simply holding
    the same coins = -L * (sqrt1 - sqrt0)**2 / sqrt0 (in token1). This does not
    depend on how wide the range is, so fee/loss is the purest test of whether
    providing liquidity pays.
    """
    s0 = df.sqrt.shift(1)
    out = pd.DataFrame(index=df.index)
    out["fee"] = df.f1 + df.f0 * df.price
    out["loss"] = (df.sqrt - s0) ** 2 / s0
    out["ret"] = np.log(df.price / df.price.shift(1))
    # one unit of liquidity spread over the full range is worth 2*sqrt(price):
    # dividing by it gives "fraction of capital per interval" (loss_n ~ ret**2 / 8)
    out["fee_n"] = out.fee / (2 * s0)
    out["loss_n"] = out.loss / (2 * s0)
    return out.iloc[1:]


def amounts(L: float, s: float, sa: float, sb: float) -> tuple[float, float]:
    s = min(max(s, sa), sb)
    return L * (1 / s - 1 / sb), L * (s - sa)


def liquidity_for_value(value: float, s: float, sa: float, sb: float) -> float:
    x, y = amounts(1.0, s, sa, sb)
    return value / (x * s * s + y)


@dataclass
class Costs:
    gas_usd: float = 0.03        # burn + collect + swap + mint on Base (measured ~0.006 gwei)
    swap_fee: float = 0.0005     # pool fee paid on the part that must be swapped
    slippage: float = 0.0002     # extra price impact / MEV allowance on swaps


def simulate(df: pd.DataFrame, width, capital: float = 60.0, costs: Costs = Costs(),
             active=None, recenter_every: int | None = None, exit_buffer: float = 0.0,
             idle_asset: str = "usdc") -> pd.DataFrame:
    """Back-test one LP position that is re-centred when the price leaves the range.

    width: half-width as a fraction (0.05 = ±5%), scalar or array aligned to df
           (the value at the moment of (re)opening is used).
    active: optional bool array; when False the position is closed and parked.
    idle_asset: 'usdc' or 'hold' (keep the coins as withdrawn) while inactive.
    Returns equity curve with columns value, fees, n_rebalance, in_range.
    """
    n = len(df)
    sq = df.sqrt.values
    f0 = df.f0.values
    f1 = df.f1.values
    width = np.full(n, width, dtype=float) if np.isscalar(width) else np.asarray(width, dtype=float)
    active = np.ones(n, dtype=bool) if active is None else np.asarray(active, dtype=bool)

    cash = capital       # token1 not in the position
    coin = 0.0           # token0 not in the position
    L = sa = sb = 0.0
    opened_at = -1
    fees_cum = 0.0
    cost_cum = 0.0
    nreb = 0
    val = np.empty(n)
    fees = np.empty(n)
    costs_arr = np.empty(n)
    rebs = np.empty(n)
    inr = np.zeros(n, dtype=bool)

    def close(i):
        nonlocal L, cash, coin
        if L > 0:
            x, y = amounts(L, sq[i], sa, sb)
            coin += x
            cash += y
            L = 0.0

    def open_(i):
        nonlocal L, sa, sb, cash, coin, opened_at, cost_cum, nreb
        s = sq[i]
        p = s * s
        w = max(width[i], 0.0011)
        sa_, sb_ = s * np.sqrt(1 - w) if w < 1 else s * 1e-3, s * np.sqrt(1 + w)
        total = cash + coin * p - costs.gas_usd
        # target split for the new range
        x1, y1 = amounts(1.0, s, sa_, sb_)
        frac_coin = x1 * p / (x1 * p + y1)
        swap = abs(coin * p - frac_coin * total)
        c = swap * (costs.swap_fee + costs.slippage)
        total -= c
        cost_cum += c + costs.gas_usd
        L = liquidity_for_value(total, s, sa_, sb_)
        sa, sb = sa_, sb_
        cash = coin = 0.0
        opened_at = i
        nreb += 1

    def park(i):
        nonlocal cash, coin, cost_cum
        if idle_asset == "usdc" and coin > 0:
            p = sq[i] ** 2
            c = coin * p * (costs.swap_fee + costs.slippage) + costs.gas_usd
            cash += coin * p - c
            cost_cum += c
            coin = 0.0

    for i in range(n):
        s = sq[i]
        if L > 0 and i > 0:
            s0 = sq[i - 1]
            lo, hi = (s0, s) if s0 <= s else (s, s0)
            if hi > lo:
                frac = max(0.0, min(hi, sb) - max(lo, sa)) / (hi - lo)
            else:
                frac = 1.0 if sa <= s <= sb else 0.0
            if frac > 0:
                fee = L * frac * (f1[i] + f0[i] * s * s)
                cash += fee
                fees_cum += fee
        if L > 0:
            out = s < sa * (1 - exit_buffer) or s > sb * (1 + exit_buffer)
            stale = recenter_every is not None and i - opened_at >= recenter_every
            if not active[i]:
                close(i)
                park(i)
            elif out or stale:
                close(i)
                open_(i)
        elif active[i]:
            open_(i)
        x, y = amounts(L, s, sa, sb) if L > 0 else (0.0, 0.0)
        val[i] = cash + y + (coin + x) * s * s
        fees[i] = fees_cum
        costs_arr[i] = cost_cum
        rebs[i] = nreb
        inr[i] = L > 0 and sa <= s <= sb
    return pd.DataFrame({"value": val, "fees": fees, "costs": costs_arr, "n_open": rebs, "in_range": inr},
                        index=df.index)
