"""Settings of the Quant V2-V5 pipeline (machine-learning layer on top of the V1 lab)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class QuantSettings:
    assets: tuple[str, ...] = ("EURUSD", "XAUUSD", "BTCUSD")  # keys of settings.INSTRUMENTS
    single_asset: str = "BTCUSD"          # V1-V3 run on one market
    timeframe: str = "1h"                 # signal timeframe; fills are simulated on 15m bars
    # triple barrier
    sl_mult: float = 1.5                  # stop = sl_mult x ATR(14)
    pt_mult: float = 1.6                  # target = pt_mult x stop distance (V2/V3 plain exit)
    max_holding_bars: int = 24            # vertical barrier, in signal bars
    mae_limit: float = 0.85               # V3+: label 1 only if the open loss stayed above -0.85R
    high_mae_weight: float = 3.0          # V4+: weight of losers that went through the MAE limit
    # walk-forward
    train_months: int = 6
    test_months: int = 1
    prob_threshold: float = 0.55
    conformal_alpha: float = 0.10
    calibration_frac: float = 0.25
    # prop firm (account of US$ 10,000, 2-step)
    account_size: float = 10_000.0
    phase1_target: float = 0.08
    phase2_target: float = 0.05
    daily_dd_limit: float = 0.05
    max_dd_limit: float = 0.10
    hard_daily_kill: float = 0.032
    max_portfolio_open_risk: float = 0.012
    profit_split: float = 0.80
    challenge_fee: float = 50.0
    payout_trigger: float = 0.045         # V5 funded account: withdraw when the cushion reaches +4.5%
    # filters
    amihud_block_pct: float = 0.85
    vpin_block_pct: float = 0.90
    rollover_block: tuple[float, float] = (21.75, 23.25)  # UTC hours with no new entries
    spread_spike: float = 1.8             # block when the bar range is this many times its average
    corr_limit: float = 0.55
    absorption_limit: float = 0.75
    # Monte Carlo
    mc_paths: int = 10_000
    mc_block: int = 6
    seed: int = 11
    state_db: Path = ROOT / "state" / "quant_v5_state.db"
    out_dir: Path = ROOT / "output"


Q = QuantSettings()
