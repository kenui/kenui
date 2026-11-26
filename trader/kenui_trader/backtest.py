"""Bar-by-bar backtester for long-only spot day trading.

Rules that keep results honest:
  * A signal on bar t is filled at the OPEN of bar t+1 (no look-ahead).
  * Every fill pays the taker fee and slippage, on entry and on exit.
  * If stop-loss and take-profit are both touched inside one bar,
    the stop is assumed to fill first (worst case).
  * Orders below Binance's minimum notional are skipped.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Costs:
    fee: float = 0.001        # 0.10% Binance spot taker (0.075% paying fees in BNB)
    slippage: float = 0.0005  # 0.05% per fill; raise for thin coins
    min_notional: float = 5.0  # USDT


@dataclass
class Risk:
    position_frac: float = 1.0     # fraction of equity per trade
    stop_loss: float | None = 0.02  # 2% below entry
    take_profit: float | None = 0.04
    max_bars: int | None = None     # time stop
    daily_loss_limit: float | None = 0.05  # stop trading for the day after -5%


@dataclass
class Result:
    equity: pd.Series
    trades: pd.DataFrame
    stats: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return "\n".join(f"{k:>22}: {v}" for k, v in self.stats.items())


def run(df: pd.DataFrame, entries: pd.Series, exits: pd.Series | None = None,
        capital: float = 60.0, costs: Costs = Costs(), risk: Risk = Risk(),
        bars_per_year: float | None = None) -> Result:
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    ent = entries.reindex(df.index).fillna(False).to_numpy(bool)
    ext = (exits.reindex(df.index).fillna(False).to_numpy(bool)
           if exits is not None else np.zeros(len(df), bool))
    days = df.index.normalize()

    cash, qty = capital, 0.0
    entry_px = entry_cost = 0.0
    entry_i = -1
    day_start_eq, cur_day, halted = capital, None, False
    eq = np.empty(len(df))
    trades = []

    def close_pos(i, px, reason):
        nonlocal cash, qty
        fill = px * (1 - costs.slippage)
        proceeds = qty * fill * (1 - costs.fee)
        trades.append({
            "entry_time": df.index[entry_i], "exit_time": df.index[i],
            "entry_px": entry_px, "exit_px": fill, "qty": qty,
            "pnl": proceeds - entry_cost, "ret": proceeds / entry_cost - 1,
            "bars": i - entry_i, "reason": reason,
        })
        cash += proceeds
        qty = 0.0

    for i in range(len(df)):
        if days[i] != cur_day:
            cur_day = days[i]
            day_start_eq = cash + qty * o[i]
            halted = False

        # 1) execute signals from the previous bar at this bar's open
        if i > 0:
            if qty > 0 and ext[i - 1]:
                close_pos(i, o[i], "signal")
            elif qty == 0 and ent[i - 1] and not halted:
                budget = cash * risk.position_frac
                if budget >= costs.min_notional:
                    entry_px = o[i] * (1 + costs.slippage)
                    qty = budget * (1 - costs.fee) / entry_px
                    entry_cost = budget
                    cash -= budget
                    entry_i = i

        # 2) protective exits inside the bar
        if qty > 0:
            sl = entry_px * (1 - risk.stop_loss) if risk.stop_loss else None
            tp = entry_px * (1 + risk.take_profit) if risk.take_profit else None
            if sl is not None and l[i] <= sl:
                close_pos(i, min(sl, o[i]), "stop")  # gap below stop fills at open
            elif tp is not None and h[i] >= tp:
                close_pos(i, max(tp, o[i]), "target")
            elif risk.max_bars and i - entry_i >= risk.max_bars:
                close_pos(i, c[i], "time")

        eq[i] = cash + qty * c[i]
        if risk.daily_loss_limit and eq[i] <= day_start_eq * (1 - risk.daily_loss_limit):
            if qty > 0:
                close_pos(i, c[i], "daily_limit")
                eq[i] = cash
            halted = True

    if qty > 0:
        close_pos(len(df) - 1, c[-1], "end")
        eq[-1] = cash

    equity = pd.Series(eq, index=df.index, name="equity")
    tdf = pd.DataFrame(trades)
    return Result(equity, tdf, stats(equity, tdf, capital, df, bars_per_year))


def _bars_per_year(index: pd.DatetimeIndex) -> float:
    step = pd.Series(index).diff().median()
    return pd.Timedelta(days=365) / step if pd.notna(step) and step > pd.Timedelta(0) else 365.0


def stats(equity: pd.Series, trades: pd.DataFrame, capital: float,
          df: pd.DataFrame, bars_per_year: float | None = None) -> dict:
    bpy = bars_per_year or _bars_per_year(equity.index)
    r = equity.pct_change().dropna()
    dd = equity / equity.cummax() - 1
    n = len(trades)
    wins = trades[trades["pnl"] > 0] if n else trades
    losses = trades[trades["pnl"] <= 0] if n else trades
    gross_win = wins["pnl"].sum() if n else 0.0
    gross_loss = -losses["pnl"].sum() if n else 0.0
    days = max((equity.index[-1] - equity.index[0]).days, 1)
    bh = df["close"].iloc[-1] / df["close"].iloc[0] - 1
    return {
        "period": f"{equity.index[0]:%Y-%m-%d} -> {equity.index[-1]:%Y-%m-%d} ({days}d)",
        "final_equity": round(float(equity.iloc[-1]), 2),
        "total_return_%": round((equity.iloc[-1] / capital - 1) * 100, 2),
        "buy_and_hold_%": round(bh * 100, 2),
        "max_drawdown_%": round(float(dd.min()) * 100, 2),
        "sharpe": round(float(r.mean() / r.std() * np.sqrt(bpy)), 2) if r.std() > 0 else 0.0,
        "trades": n,
        "trades_per_day": round(n / days, 2),
        "win_rate_%": round(len(wins) / n * 100, 1) if n else 0.0,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else float("inf") if gross_win > 0 else 0.0,
        "avg_trade_%": round(trades["ret"].mean() * 100, 3) if n else 0.0,
        "exposure_%": round(trades["bars"].sum() / len(equity) * 100, 1) if n else 0.0,
    }


def walk_forward(df: pd.DataFrame, strategy, grid: list[dict], n_splits: int = 4,
                 train_frac: float = 0.7, score: str = "sharpe", **run_kwargs) -> pd.DataFrame:
    """Optimize on each train window, then judge only on the following unseen window.

    `strategy(df, **params)` must return (entries, exits, risk_overrides_dict).
    """
    rows = []
    edges = np.linspace(0, len(df), n_splits + 1, dtype=int)
    for k in range(n_splits):
        chunk = df.iloc[edges[k]:edges[k + 1]]
        cut = int(len(chunk) * train_frac)
        train, test = chunk.iloc[:cut], chunk.iloc[cut:]
        best, best_score = None, -np.inf
        for params in grid:
            e, x, rk = strategy(train, **params)
            res = run(train, e, x, risk=Risk(**{**Risk().__dict__, **rk}), **run_kwargs)
            s = res.stats[score] if res.stats["trades"] >= 10 else -np.inf
            if s > best_score:
                best, best_score = params, s
        if best is None:
            continue
        # compute signals with warm-up history so indicators are ready at the test start
        warm = df.iloc[max(0, edges[k] + cut - 2000):edges[k + 1]]
        e, x, rk = strategy(warm, **best)
        e, x = e.reindex(test.index), (x.reindex(test.index) if x is not None else None)
        res = run(test, e, x, risk=Risk(**{**Risk().__dict__, **rk}), **run_kwargs)
        rows.append({"split": k, "params": best, f"train_{score}": best_score, **res.stats})
    return pd.DataFrame(rows)
