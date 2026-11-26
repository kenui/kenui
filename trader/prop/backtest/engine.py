"""Account-level, bar-by-bar backtest for one or several markets, long and short.

Same honesty rules as `kenui_trader.backtest`:
  * a signal on bar t is filled at the OPEN of the next bar (no look-ahead);
  * every fill pays the instrument's cost (spread + commission + slippage);
  * when stop and target are both inside one bar, the stop is assumed first;
  * a gap through the stop fills at the open (worse than the stop);
  * positions held past 22:00 UTC pay the overnight swap for each night;
  * drawdown limits are checked against the worst equity inside each bar, with every open
    position at its adverse extreme at the same time.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from prop.config.settings import INSTRUMENTS, SETTINGS, Instrument, PropRules, RiskConfig
from prop.risk.risk_manager import RiskManager, news_windows
from prop.strategies.indicators import atr


@dataclass
class BacktestResult:
    equity: pd.Series      # equity at each bar close
    worst: pd.Series       # worst equity inside each bar
    day_start: pd.Series   # equity the daily-loss rule measures from
    trades: pd.DataFrame
    locks: list[tuple[pd.Timestamp, str]]
    initial: float


class _Position:
    __slots__ = ("side", "units", "entry_fill", "stop", "tp", "entry_k", "max_bars", "risk_money",
                 "worst_px", "engine", "entry_time")


def run(bars: dict[str, pd.DataFrame], signals: dict[str, pd.DataFrame], risk: RiskConfig,
        rules: PropRules = SETTINGS.rules, instruments: dict[str, Instrument] = INSTRUMENTS) -> BacktestResult:
    initial = rules.account_size
    names = list(bars)
    union = bars[names[0]].index
    for n in names[1:]:
        union = union.union(bars[n].index)
    n_union = len(union)
    day_id = pd.factorize(union.tz_convert(rules.day_timezone).normalize())[0]
    blocked = news_windows(union) if risk.news_shield else np.zeros(n_union, bool)

    S = []  # per-symbol arrays
    for n in names:
        df, sg = bars[n], signals[n].reindex(bars[n].index)
        t = df.index
        gap_next = np.zeros(len(df), bool)
        if instruments[n].closes_weekend and len(df) > 1:
            gap_next[:-1] = (t[1:] - t[:-1]) > pd.Timedelta(hours=2)
        a = atr(df, 14).to_numpy()
        wide = np.zeros(len(df), bool)
        if risk.max_bar_range_atr:
            wide = (df["high"] - df["low"]).to_numpy() > risk.max_bar_range_atr * np.nan_to_num(a, nan=np.inf)
        night = ((t - pd.Timedelta(hours=22)).floor("D").asi8 // 86_400_000_000_000
                 if t.unit == "ns" else (t - pd.Timedelta(hours=22)).floor("D").as_unit("s").asi8 // 86_400)
        S.append(dict(
            name=n, night=night.tolist(), inst=instruments[n], upos=union.get_indexer(t).tolist(), k=0, n=len(df), t=t,
            o=df["open"].tolist(), h=df["high"].tolist(), l=df["low"].tolist(), c=df["close"].tolist(),
            side=sg["side"].fillna(0).astype(int).tolist(), sd=sg["stop_dist"].tolist(),
            tp=sg["tp_dist"].tolist(), mb=sg["max_bars"].fillna(0).astype(int).tolist(),
            eng=sg["engine"].fillna("").tolist(), gap=gap_next.tolist(), wide=wide.tolist(),
            pos=None, pending=-1, last_c=float("nan")))

    rm = RiskManager(risk, initial)
    balance = initial
    eq = np.empty(n_union)
    worst = np.empty(n_union)
    dstart = np.empty(n_union)
    trades: list[dict] = []
    prev_eq, cur_day, day_start = initial, -1, initial

    def close(s: dict, k: int, px: float, reason: str) -> None:
        nonlocal balance
        p: _Position = s["pos"]
        fill = px * (1 - p.side * s["inst"].cost_per_side)
        nights = s["night"][k] - s["night"][p.entry_k]
        pnl = p.units * p.side * (fill - p.entry_fill) - p.units * p.entry_fill * s["inst"].swap_per_night * nights
        balance += pnl
        mae = p.units * p.side * (p.worst_px - p.entry_fill)
        trades.append(dict(symbol=s["name"], engine=p.engine, side=p.side, entry_time=p.entry_time,
                           exit_time=s["t"][k], entry=p.entry_fill, exit=fill, units=p.units,
                           risk_money=p.risk_money, pnl=pnl, r=pnl / p.risk_money,
                           mae_r=min(mae, pnl) / p.risk_money, bars=k - p.entry_k, reason=reason,
                           ret_notional=pnl / (p.units * p.entry_fill)))
        rm.on_trade_closed(pnl)
        s["pos"] = None

    for i in range(n_union):
        if day_id[i] != cur_day:
            cur_day = day_id[i]
            day_start = max(balance, prev_eq)
            rm.new_day(day_start)
        floating = floating_worst = 0.0
        for s in S:
            k = s["k"]
            if k >= s["n"] or s["upos"][k] != i:
                p = s["pos"]
                if p is not None:  # market closed for this symbol: mark at last close
                    f = p.units * p.side * (s["last_c"] - p.entry_fill)
                    floating += f
                    floating_worst += f
                continue
            s["k"] = k + 1
            o, h, l, c = s["o"][k], s["h"][k], s["l"][k], s["c"][k]
            p = s["pos"]
            # 1) the news shield flattens what is open when a blocked window starts
            if p is not None and blocked[i]:
                close(s, k, o, "news")
                p = None
            # 2) fill the signal from the previous bar at this open
            j = s["pending"]
            s["pending"] = -1
            if p is None and j >= 0 and rm.can_open() and not blocked[i] and not s["wide"][j]:
                sd, side = s["sd"][j], s["side"][j]
                if sd == sd and sd > 0:
                    cost = s["inst"].cost_per_side
                    units, risk_money = rm.position_units(balance, o, sd, s["inst"].max_leverage)
                    if units > 0:
                        p = _Position()
                        p.side, p.units, p.risk_money = side, units, risk_money
                        p.entry_fill = o * (1 + side * cost)
                        p.stop, p.tp = o - side * sd, o + side * s["tp"][j]
                        p.entry_k, p.max_bars, p.engine = k, s["mb"][j], s["eng"][j]
                        p.worst_px, p.entry_time = p.entry_fill, s["t"][k]
                        s["pos"] = p
            # 3) protective exits inside the bar (stop first)
            if p is not None:
                adverse = l if p.side > 0 else h
                if p.side * (adverse - p.worst_px) < 0:
                    p.worst_px = adverse
                hit_stop = l <= p.stop if p.side > 0 else h >= p.stop
                hit_tp = h >= p.tp if p.side > 0 else l <= p.tp
                if hit_stop:
                    gapped = o <= p.stop if p.side > 0 else o >= p.stop
                    close(s, k, o if gapped else p.stop, "stop")
                elif hit_tp:
                    gapped = o >= p.tp if p.side > 0 else o <= p.tp
                    close(s, k, o if gapped else p.tp, "target")
                elif p.max_bars and k - p.entry_k + 1 >= p.max_bars:
                    close(s, k, c, "time")
                elif s["gap"][k]:
                    close(s, k, c, "weekend")
                else:
                    floating += p.units * p.side * (c - p.entry_fill)
                    floating_worst += p.units * p.side * (adverse - p.entry_fill)
            # 4) a signal on this bar waits for the next open (never across the weekend gap)
            if s["side"][k] != 0 and not s["gap"][k]:
                s["pending"] = k
            s["last_c"] = c

        e, w = balance + floating, balance + min(floating, floating_worst)
        if rm.on_equity(union[i], w):
            for s in S:
                if s["pos"] is not None:
                    kk = s["k"] - 1
                    close(s, kk, s["last_c"], "lock")
                s["pending"] = -1
            e = balance
        eq[i], worst[i], dstart[i] = e, min(w, e), day_start
        prev_eq = e

    for s in S:
        if s["pos"] is not None:
            close(s, s["n"] - 1, s["last_c"], "end")
    if n_union:
        eq[-1] = balance
        worst[-1] = min(worst[-1], balance)
    cols = ["symbol", "engine", "side", "entry_time", "exit_time", "entry", "exit", "units", "risk_money",
            "pnl", "r", "mae_r", "bars", "reason", "ret_notional"]
    return BacktestResult(pd.Series(eq, union, name="equity"), pd.Series(worst, union, name="worst"),
                          pd.Series(dstart, union, name="day_start"),
                          pd.DataFrame(trades, columns=cols), rm.locks, initial)
