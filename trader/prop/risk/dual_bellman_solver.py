"""V5: two solvers for the two lives of a prop account.

Solver A (evaluation): `bellman_barrier_controller.solve_evaluation`, first passage to the
target before the loss barriers.
Solver B (funded account, De Finetti dividend problem): the account is a surplus process; the
trader chooses the risk per trade (0.35% to 0.55%) and withdraws 80% of the profit whenever the
cushion reaches the payout trigger. The value is the expected discounted sum of withdrawals
before the account is lost at -10%.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from prop.config.quant import Q
from prop.risk.bellman_barrier_controller import X_STEP, BarrierPolicy, solve_evaluation  # noqa: F401

FUNDED_ACTIONS = np.array([0.0035, 0.0045, 0.0055])


@dataclass
class HarvestPolicy:
    x_grid: np.ndarray
    risk: np.ndarray
    value: np.ndarray       # expected discounted withdrawals, as a fraction of the account
    trigger: float

    def lookup(self, x: np.ndarray) -> np.ndarray:
        ix = np.clip(np.rint((x - self.x_grid[0]) / X_STEP).astype(int), 0, len(self.x_grid) - 1)
        return self.risk[ix]


def solve_funded(r_values: np.ndarray, r_probs: np.ndarray, trigger: float = Q.payout_trigger,
                 max_loss: float = Q.max_dd_limit, split: float = Q.profit_split, discount: float = 0.9995,
                 sweeps: int = 20000, tol: float = 1e-9,
                 actions: np.ndarray = FUNDED_ACTIONS) -> HarvestPolicy:
    xg = np.arange(-max_loss, trigger + X_STEP / 2, X_STEP)
    n = len(xg)
    zero = int(np.rint((0 - xg[0]) / X_STEP))
    V = np.zeros(n)
    best = np.zeros(n, int)

    def value_at(Vcur: np.ndarray, xn: np.ndarray) -> np.ndarray:
        paid = xn >= trigger
        dead = xn <= -max_loss
        cont = np.interp(np.clip(xn, xg[0], xg[-1]), xg, Vcur)
        harvest = split * xn + Vcur[zero]          # withdraw the profit share, restart at the base balance
        return np.where(dead, 0.0, np.where(paid, harvest, cont))

    rv, pv = np.asarray(r_values, float)[:, None], np.asarray(r_probs, float)[:, None]
    for _ in range(sweeps):
        q = np.stack([(pv * value_at(V, xg[None, :] + f * rv)).sum(axis=0) for f in actions]) * discount
        new = q.max(axis=0)
        new[0] = 0.0
        best = q.argmax(axis=0)
        done = np.abs(new - V).max() < tol
        V = new
        if done:
            break
    return HarvestPolicy(xg, np.asarray(actions)[best], V, trigger)
