"""V4: optimal risk as a function of the distance to the barriers (dynamic programming).

State: x_total (account result since the start of the phase) and x_daily (result of the
current day). Action: fraction of the account risked on the next trade. Value: probability
of touching the profit target before the total-loss barrier, discounted a little per trade so
that "never trade" is not optimal (without a discount, a strategy with a positive edge maximises
its pass probability by betting as small as possible and taking forever).
The trade-outcome distribution is an input: real R results re-centred on a design edge.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from prop.config.quant import Q

ACTIONS = np.array([0.0025, 0.005, 0.0075, 0.010])
X_STEP, D_STEP = 0.001, 0.0025


@dataclass
class BarrierPolicy:
    x_grid: np.ndarray       # total result
    d_grid: np.ndarray       # daily result
    risk: np.ndarray         # optimal risk fraction, shape (len(x_grid), len(d_grid))
    value: np.ndarray        # probability-like value of each state
    target: float

    def lookup(self, x: np.ndarray, d: np.ndarray) -> np.ndarray:
        ix = np.clip(np.rint((x - self.x_grid[0]) / X_STEP).astype(int), 0, len(self.x_grid) - 1)
        idd = np.clip(np.rint((d - self.d_grid[0]) / D_STEP).astype(int), 0, len(self.d_grid) - 1)
        return self.risk[ix, idd]


def outcome_distribution(r: np.ndarray, design_edge: float | None = None, bin_r: float = 0.1) -> tuple[np.ndarray, np.ndarray]:
    """Histogram of R results, optionally shifted so that its mean equals `design_edge`."""
    r = np.asarray(r, float)
    if design_edge is not None:
        r = r - r.mean() + design_edge
    bins = np.rint(r / bin_r).astype(int)
    vals, counts = np.unique(bins, return_counts=True)
    return vals * bin_r, counts / counts.sum()


def solve_evaluation(r_values: np.ndarray, r_probs: np.ndarray, target: float,
                     max_loss: float = Q.max_dd_limit, daily_kill: float = Q.hard_daily_kill,
                     trades_per_day: float = 2.0, discount: float = 0.999, sweeps: int = 3000,
                     tol: float = 1e-7, actions: np.ndarray = ACTIONS) -> BarrierPolicy:
    """Value iteration on the (x_total, x_daily) grid."""
    xg = np.arange(-max_loss, target + X_STEP / 2, X_STEP)
    dg = np.arange(-Q.daily_dd_limit, Q.daily_dd_limit + D_STEP / 2, D_STEP)
    nx, nd = len(xg), len(dg)
    X, D = np.meshgrid(xg, dg, indexing="ij")
    q_end = min(1.0, 1.0 / trades_per_day)       # chance that this trade is the last of the day
    zero_d = int(np.rint((0 - dg[0]) / D_STEP))
    V = np.clip((X + max_loss) / (target + max_loss), 0, 1)
    V[-1, :], V[0, :] = 1.0, 0.0

    def interp(Vcur: np.ndarray, xn: np.ndarray, dn: np.ndarray) -> np.ndarray:
        fx = np.clip((xn - xg[0]) / X_STEP, 0, nx - 1)
        i0 = np.floor(fx).astype(int)
        i1 = np.minimum(i0 + 1, nx - 1)
        wx = fx - i0
        j = np.clip(np.rint((dn - dg[0]) / D_STEP).astype(int), 0, nd - 1)
        return (1 - wx) * Vcur[i0, j] + wx * Vcur[i1, j]

    best = np.zeros((nx, nd), int)
    for _ in range(sweeps):
        q = np.empty((len(actions), nx, nd))
        for a, f in enumerate(actions):
            acc = np.zeros((nx, nd))
            for rv, pv in zip(r_values, r_probs):
                step = f * rv
                dn = D + step
                killed = dn <= -daily_kill                  # the tick guard closes the day at the kill level
                xn = np.where(killed, X + (-daily_kill - D), X + step)
                win, dead = xn >= target, xn <= -max_loss
                same_day = interp(V, xn, np.where(killed, 0.0, dn))
                next_day = interp(V, xn, np.zeros_like(dn))
                cont = np.where(killed, next_day, (1 - q_end) * same_day + q_end * next_day)
                acc += pv * np.where(win, 1.0, np.where(dead, 0.0, discount * cont))
            q[a] = acc
        new = q.max(axis=0)
        new[-1, :], new[0, :] = 1.0, 0.0
        best = q.argmax(axis=0)
        done = np.abs(new - V).max() < tol
        V = new
        if done:
            break
    _ = zero_d
    return BarrierPolicy(xg, dg, np.asarray(actions)[best], V, target)


def zone(x: np.ndarray, target: float) -> np.ndarray:
    """Payoff-shaping zones, scaled to the phase target (written for the 8% phase):
    0 neutral, 1 final stretch (>= 5.5/8 of the target), -1 deep drawdown (< -3%)."""
    z = np.zeros(len(x), int)
    z[x >= target * 5.5 / 8.0] = 1
    z[x < -0.03] = -1
    return z


def correlation_scale(corr_with_open: float, limit: float = Q.corr_limit) -> float:
    """Lot multiplier for a new position that is correlated with one already open."""
    c = abs(corr_with_open)
    return 1.0 if c <= limit else max(0.0, 1.0 - c)
