"""Risk manager: position sizing and the safety locks that keep a prop account alive.

The same object is meant to drive a live trader later: call `new_day`, ask `can_open` and
`risk_fraction` before each order, report `on_trade_closed`, and feed `on_equity` every tick/bar.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from prop.config.settings import SETTINGS, RiskConfig

NY = ZoneInfo("America/New_York")


class RiskManager:
    def __init__(self, cfg: RiskConfig, initial_balance: float) -> None:
        self.cfg = cfg
        self.initial = initial_balance
        self.day_start_equity = initial_balance
        self.day_locked = False
        self.halted = False          # max-drawdown lock: the system stays off
        self.losses_today = 0        # consecutive stops in the current day
        self.win_streak = 0
        self.locks: list[tuple[pd.Timestamp, str]] = []

    def new_day(self, equity: float) -> None:
        self.day_start_equity = equity
        self.day_locked = False
        self.losses_today = 0

    def can_open(self) -> bool:
        return not (self.halted or self.day_locked)

    def risk_fraction(self) -> float:
        """Fraction of equity to risk on the next trade (dynamic lot)."""
        r = self.cfg.risk_per_trade
        if self.cfg.halve_after_losses and self.losses_today >= self.cfg.halve_after_losses:
            r *= 0.5
        elif self.win_streak >= 2:
            r *= self.cfg.win_streak_boost
        return min(r, self.cfg.max_risk_per_trade)

    def position_units(self, equity: float, price: float, stop_dist: float, max_leverage: float) -> tuple[float, float]:
        """(units, money at risk). Size so a stop costs `risk_fraction`, capped by leverage."""
        risk_money = equity * self.risk_fraction()
        units = min(risk_money / stop_dist, equity * max_leverage / price)
        return units, risk_money

    def on_trade_closed(self, pnl: float) -> None:
        if pnl < 0:
            self.losses_today += 1
            self.win_streak = 0
        else:
            self.losses_today = 0
            self.win_streak += 1

    def on_equity(self, when: pd.Timestamp, equity: float) -> bool:
        """Returns True when every position must be closed now (a lock just fired)."""
        cfg = self.cfg
        if cfg.max_drawdown_lock and not self.halted and equity <= self.initial * (1 - cfg.max_drawdown_lock):
            self.halted = True
            self.locks.append((when, "max_drawdown"))
            return True
        if cfg.daily_hard_stop and not self.day_locked and \
                equity <= self.day_start_equity - self.initial * cfg.daily_hard_stop:
            self.day_locked = True
            self.locks.append((when, "daily_stop"))
            return True
        return False


def news_windows(index: pd.DatetimeIndex, minutes_before: int = 30, minutes_after: int = 30) -> np.ndarray:
    """True on bars inside a scheduled high-impact window (no calendar API is reachable here,
    so the shield uses rules): every weekday 08:30 New York (most US data, incl. NFP and CPI)
    and FOMC days 14:00 New York. A bar is blocked when it overlaps [t - before, t + after]."""
    step = (index[1] - index[0]) if len(index) > 1 else pd.Timedelta(minutes=15)
    local = index.tz_convert(NY)
    minute_of_day = local.hour * 60 + local.minute
    bar_end = minute_of_day + step.total_seconds() / 60

    def overlaps(event_min: int) -> np.ndarray:
        return (bar_end > event_min - minutes_before) & (minute_of_day < event_min + minutes_after)

    weekday = local.weekday < 5
    blocked = weekday & overlaps(8 * 60 + 30)
    fomc = {datetime.strptime(d, "%Y-%m-%d").date() for d in SETTINGS.fomc_days}
    is_fomc = np.array([d in fomc for d in local.date]) if fomc else np.zeros(len(index), bool)
    return np.asarray(blocked | (is_fomc & overlaps(14 * 60)))
