"""Global parameters: instruments, simulated costs, risk limits and prop-firm rules.

Everything a later live trader needs to agree with the backtest lives here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Instrument:
    """One tradable market and how it is simulated."""

    name: str            # label used in reports (what the prop firm calls it)
    source: str          # Binance symbol used as the price proxy
    market: str          # "spot" or "futures" (Binance public data folder)
    cost_per_side: float  # half spread + commission + slippage, as a fraction of price
    max_leverage: float  # notional / equity cap, as prop firms apply per asset class
    swap_per_night: float  # overnight financing as a fraction of notional, charged per night held
    closes_weekend: bool  # forex and gold stop Fri 22:00 UTC -> Sun 22:00 UTC


# Costs are what a typical prop-firm MT5 account charges, slightly pessimistic:
#   EUR/USD ~0.8 pip per side all-in, XAU/USD ~US$0.50, BTC/USD ~0.04%.
# Swaps are charged on both directions (pessimistic): ~1.5%/yr EUR, ~5.5%/yr gold, ~20%/yr BTC.
INSTRUMENTS: dict[str, Instrument] = {
    "EURUSD": Instrument("EURUSD", "EURUSDT", "spot", 0.00007, 30.0, 0.00004, True),
    "XAUUSD": Instrument("XAUUSD", "PAXGUSDT", "spot", 0.00015, 20.0, 0.00015, True),
    "BTCUSD": Instrument("BTCUSD", "BTCUSDT", "spot", 0.00040, 2.0, 0.00055, False),
}


@dataclass(frozen=True)
class PropRules:
    """Evaluation rules of a typical 2-step challenge (FundedNext Stellar / The5ers High Stakes)."""

    account_size: float = 5_000.0
    target_phase1: float = 0.08
    target_phase2: float = 0.05
    max_daily_loss: float = 0.05   # of initial balance, measured from the day's starting equity
    max_total_loss: float = 0.10   # static, from initial balance
    min_trading_days: int = 5
    day_timezone: str = "Europe/Prague"  # prop servers reset the day at midnight CE(S)T
    profit_split: float = 0.80
    payout_every_days: int = 14
    fee_usd: float = 60.0          # challenge fee + EA add-on, refunded with the first payout


@dataclass(frozen=True)
class RiskConfig:
    """Risk manager switches. `plain()` is used for runs 1-3, `prop()` for run 4."""

    risk_per_trade: float = 0.01
    max_risk_per_trade: float = 0.01
    daily_hard_stop: float | None = None   # lock the day at this loss (fraction of initial balance)
    max_drawdown_lock: float | None = None  # stop the system at this total loss
    halve_after_losses: int | None = None  # consecutive stops in the same day before halving risk
    win_streak_boost: float = 1.0          # multiply risk after two straight wins (capped at max)
    news_shield: bool = False              # block entries / flatten around scheduled news
    max_bar_range_atr: float | None = None  # skip entries after a bar wider than k x ATR (spread proxy)

    @staticmethod
    def plain(risk: float = 0.01) -> "RiskConfig":
        return RiskConfig(risk_per_trade=risk, max_risk_per_trade=risk)

    @staticmethod
    def prop(risk: float = 0.0075) -> "RiskConfig":
        return RiskConfig(risk_per_trade=risk, max_risk_per_trade=0.01, daily_hard_stop=0.03,
                          max_drawdown_lock=0.06, halve_after_losses=2, win_streak_boost=1.25,
                          news_shield=True, max_bar_range_atr=3.0)


@dataclass(frozen=True)
class Settings:
    timeframe: str = "15m"
    start: date = date(2023, 1, 1)
    end: date = date(2026, 11, 24)
    in_sample_frac: float = 0.70
    rules: PropRules = field(default_factory=PropRules)
    # Scheduled FOMC decision days (14:00 New York). NFP is derived (first Friday 08:30 New York).
    fomc_days: tuple[str, ...] = (
        "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20",
        "2023-11-01", "2023-12-13", "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
        "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18", "2025-01-29", "2025-03-19",
        "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
        "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16",
        "2026-10-28", "2026-12-09",
    )


SETTINGS = Settings()
