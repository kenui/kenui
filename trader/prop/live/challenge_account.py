"""One simulated prop-firm account, updated trade by trade (the scalar twin of the Monte Carlo
replay): Phase 1 (+8%), Phase 2 (+5%), funded with a payout whenever the cushion reaches the
trigger; -10% total ends the attempt and a new one starts. Sizing comes from the Bellman policies.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from prop.config.quant import Q
from prop.risk.bellman_barrier_controller import BarrierPolicy
from prop.risk.dual_bellman_solver import HarvestPolicy


@dataclass
class ChallengeAccount:
    phase: int = 0              # 0 = Phase 1, 1 = Phase 2, 2 = funded
    x: float = 0.0              # result since the start of the phase (fraction of the account)
    day: str = ""               # current trading day (Europe/Prague date)
    day_pnl: float = 0.0
    day_locked: bool = False
    attempts: int = 1
    passed_p1: int = 0
    funded: int = 0
    failed: int = 0
    payouts_usd: float = 0.0
    events: list = field(default_factory=list)

    def new_day(self, day: str) -> None:
        if day != self.day:
            self.day, self.day_pnl, self.day_locked = day, 0.0, False

    def risk(self, barrier: dict[int, BarrierPolicy], harvest: HarvestPolicy, open_risk: float = 0.0,
             max_open_risk: float = 0.04) -> float:
        """Fraction of the account to risk on the next trade (0 = do not trade)."""
        if self.day_locked:
            return 0.0
        x, d = np.array([self.x]), np.array([self.day_pnl])
        f = float(harvest.lookup(x)[0]) if self.phase == 2 else float(barrier[self.phase].lookup(x, d)[0])
        room = Q.hard_daily_kill + self.day_pnl
        return float(max(0.0, min(f, room, max_open_risk - open_risk)))

    def book(self, pnl: float, when: str) -> str | None:
        """Add a closed result (fraction of the account). Returns the event it caused, if any."""
        self.x += pnl
        self.day_pnl += pnl
        if self.day_pnl <= -Q.hard_daily_kill:
            self.day_locked = True
        event = None
        target = Q.phase1_target if self.phase == 0 else Q.phase2_target
        if self.x <= -Q.max_dd_limit or self.day_pnl <= -Q.daily_dd_limit:
            event = "reprovado" if self.phase < 2 else "conta financiada perdida"
            self.failed += 1
            self.attempts += 1
            self.phase, self.x = 0, 0.0
        elif self.phase == 0 and self.x >= target:
            event, self.phase, self.x = "Fase 1 aprovada", 1, 0.0
            self.passed_p1 += 1
        elif self.phase == 1 and self.x >= target:
            event, self.phase, self.x = "Fase 2 aprovada: conta financiada", 2, 0.0
            self.funded += 1
        elif self.phase == 2 and self.x >= Q.payout_trigger:
            usd = Q.profit_split * self.x * Q.account_size
            self.payouts_usd += usd
            event, self.x = f"saque de US$ {usd:.0f}", 0.0
        if event:
            self.events.append([when, event])
        return event

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ChallengeAccount":
        return cls(**d)
