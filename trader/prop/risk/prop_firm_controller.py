"""Account-aware risk controller (V3 phase switching, V4 barrier zones, V5 funded harvesting).

One configuration object describes how each version sizes a trade from the state of the prop
account. The same rules are replayed by the Monte Carlo and are what a live bridge would call.

V3 modes:
  acceleration  progress < 75% of the target: risk scaled by calibrated probability, 0.4% to 1.0%
  lock-in       progress >= 75%: risk capped at 0.35% and a stricter probability threshold
  funded        fixed 0.5% and no single day above 35% of the cycle profit (consistency rule)
Circuit breakers: no new entries once the day is down by `daily_kill`; the open trade is
liquidated at that level by the tick guard; no trade may risk more than the distance left to it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from prop.config.quant import Q
from prop.risk.bellman_barrier_controller import BarrierPolicy
from prop.risk.dual_bellman_solver import HarvestPolicy


@dataclass
class Controller:
    name: str
    threshold: float                    # minimum score (probability or conformal lower bound)
    sizing: str = "fixed"               # "fixed" | "prob" | "bellman"
    risk_lo: float = 0.005
    risk_hi: float = 0.005
    daily_kill: float = 0.03
    cap_to_kill: bool = False           # never risk more than the distance left to the daily kill
    halve_after_losses: int = 0         # consecutive stops in a day before halving risk
    max_dd_lock: float | None = None    # stop the system at this total loss (V2: 6%)
    lockin: bool = False                # V3: cap risk and raise the threshold near the target
    lockin_progress: float = 0.75
    lockin_risk: float = 0.0035
    threshold_boost: float = 0.03       # added to the threshold in lock-in / final stretch
    zones: bool = False                 # V4+: final-stretch short target and recovery mode
    recovery_risk: float = 0.0025
    funded: str = "same"                # "same" | "fixed" | "harvest"
    funded_risk: float = 0.005
    consistency: float | None = None    # max share of the cycle profit made in one day
    payout: str = "periodic"            # "periodic" (every 14 days) | "trigger" (cushion reached)
    barrier: dict[int, BarrierPolicy] = field(default_factory=dict)   # phase -> policy (0, 1)
    harvest: HarvestPolicy | None = None


def presets(thresholds: dict[str, float]) -> dict[str, Controller]:
    """The five versions. Bellman policies are attached later (they need trade statistics)."""
    return {
        "v1": Controller("V1 sinais primarios", thresholds["v1"], "fixed", 0.005, 0.005, daily_kill=0.03),
        "v2": Controller("V2 HMM + meta", thresholds["v2"], "prob", 0.0025, 0.01, daily_kill=0.03,
                         halve_after_losses=2, max_dd_lock=0.06),
        "v3": Controller("V3 calibrado + fases", thresholds["v3"], "prob", 0.004, 0.01, daily_kill=0.028,
                         cap_to_kill=True, lockin=True, funded="fixed", consistency=0.35),
        "v4": Controller("V4 conformal + Bellman", thresholds["v4"], "bellman", 0.0025, 0.01,
                         daily_kill=Q.hard_daily_kill, cap_to_kill=True, zones=True, funded="fixed",
                         consistency=0.35),
        "v5": Controller("V5 completo", thresholds["v5"], "bellman", 0.0025, 0.01,
                         daily_kill=Q.hard_daily_kill, cap_to_kill=True, zones=True, funded="harvest",
                         consistency=0.35, payout="trigger"),
        "v5s": Controller("V5 + assinaturas e ACI", thresholds["v5s"], "bellman", 0.0025, 0.01,
                          daily_kill=Q.hard_daily_kill, cap_to_kill=True, zones=True, funded="harvest",
                          consistency=0.35, payout="trigger"),
    }
