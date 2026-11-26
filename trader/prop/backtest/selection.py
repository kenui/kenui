"""From the out-of-sample event table to the trades each version would have taken.

Everything decided here depends only on the signal side (model score, vetoes, correlation,
bandit, drift monitor); what depends on the account state is applied later in the replay.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from prop.config.quant import Q
from prop.execution.contextual_bandit import LinUCB
from prop.extensions.atemporal_aci import AdaptiveConformalController
from prop.risk.bellman_barrier_controller import correlation_scale
from prop.risk.drift_monitor import CusumBrier
from prop.strategies import orthogonal_alpha

POLICIES = ("plain", "arm0", "arm1", "arm2")
SCORE = {"v1": None, "v2": "p_v2", "v3": "p_v3", "v4": "plo_v4", "v5": "plo_v5", "v5s": None}
PROB = {"v1": None, "v2": "p_v2", "v3": "p_v3", "v4": "p_v4", "v5": "p_v5", "v5s": "p_v5s"}
LABEL = {"v1": "y_v2", "v2": "y_v2", "v3": "y_v3", "v4": "y_v4", "v5": "y_v4", "v5s": "y_v4"}
# Minimum score to trade. The plain exit pays 1.6R, so it breaks even near a 42% hit rate after
# costs; 0.55 there would demand a 55% hit rate on a 35% base rate and never trade. The V4/V5
# label ("net positive with low heat") has a base rate near 50%, where 0.50 on the LOWER
# conformal bound is already a demanding bar.
THRESHOLDS = {"v1": 0.0, "v2": 0.45, "v3": 0.40, "v4": 0.50, "v5": 0.50, "v5s": 0.50}


@dataclass
class Trades:
    """Arrays the replay engine reads; one row per taken trade, in exit order."""
    R: np.ndarray        # (n, 4) net result of each exit policy, in R
    MAE: np.ndarray      # (n, 4) worst open result of each exit policy, in R
    arm: np.ndarray      # policy index chosen on the signal side
    mult: np.ndarray     # lot multiplier from correlation, HRP, systemic risk and drift monitor
    p: np.ndarray        # probability used for sizing
    score: np.ndarray    # value compared with the threshold
    new_day: np.ndarray  # first trade of a calendar day
    gap: np.ndarray      # calendar days since the previous trade
    y: np.ndarray
    time: np.ndarray
    frame: pd.DataFrame
    extra: dict | None = None   # final state of the online learners (ACI, bandit, CUSUM)

    def __len__(self) -> int:
        return len(self.arm)

    def per_year(self) -> float:
        return len(self) / max(self.gap.sum() / 365.0, 1e-9)


def vetoes(ev: pd.DataFrame, version: str) -> np.ndarray:
    ok = np.ones(len(ev), bool)
    if version in ("v3", "v4", "v5", "v5s"):
        hour = ev["entry_time"].dt.hour + ev["entry_time"].dt.minute / 60
        ok &= ~((hour >= Q.rollover_block[0]) & (hour < Q.rollover_block[1])).to_numpy()
        ok &= ~(ev["spread_spike"] > Q.spread_spike).to_numpy()
    if version in ("v4", "v5", "v5s"):
        ok &= ~(ev["amihud_pct"] > Q.amihud_block_pct).to_numpy()
        ok &= ~(ev["vpin_pct"] > Q.vpin_block_pct).to_numpy()
    if version in ("v5", "v5s"):
        ok &= orthogonal_alpha.gate(ev)
    return ok


def bandit_context(row: pd.Series) -> np.ndarray:
    width = float(row.get("pup_v5", 1.0) - row.get("plo_v5", 0.0)) if "plo_v5" in row else 0.2
    hurst = row["hurst"] if np.isfinite(row["hurst"]) else 0.5
    return np.array([1.0, row["p_compress"], row["p_trend"], row["p_shock"], width, hurst - 0.5,
                     1.0 if row["kind"] == 1 else 0.0])


def select(oos: pd.DataFrame, version: str, rolling_corr: dict[tuple[str, str], pd.Series] | None = None,
           threshold_shift: float = 0.0, fixed_arm: str | None = None) -> Trades:
    multi = version in ("v4", "v5", "v5s")
    full = version in ("v5", "v5s")
    ev = oos if multi else oos[oos["asset"] == Q.single_asset]
    ev = ev[vetoes(ev, version)]
    score = pd.Series(1.0, index=ev.index) if SCORE[version] is None else ev[SCORE[version]]
    ev = ev[score.to_numpy() >= THRESHOLDS[version] + threshold_shift].sort_values("entry_time", kind="stable")

    thr = THRESHOLDS[version] + threshold_shift
    aci = AdaptiveConformalController(alpha_target=Q.conformal_alpha) if version == "v5s" else None
    calibration = oos.attrs.get("calibration", {})
    bandit = LinUCB(7) if full and fixed_arm is None else None
    cusum = CusumBrier() if multi else None
    default_arm = fixed_arm or ("plain" if version in ("v1", "v2", "v3") else "arm1")
    open_trades: list[dict] = []       # taken trades still open
    busy_until: dict[str, pd.Timestamp] = {}
    fold_now, rows = None, []
    shadow: list[tuple] = []           # (time the outcome is known, probability, outcome)
    for _, row in ev.iterrows():
        now, asset = row["entry_time"], row["asset"]
        still = []
        for t in open_trades:           # settle what closed before this entry
            if t["exit"] <= now:
                if bandit is not None:
                    bandit.update(t["arm_i"] - 1, t["ctx"], LinUCB.reward(t["r"], t["mae"]))
                if cusum is not None:
                    cusum.update(t["p"], t["y"])
            else:
                still.append(t)
        open_trades = still
        if aci is not None:             # every vetted signal teaches the bound once its outcome is known,
            due = [s for s in shadow if s[0] <= now]          # taken or not ("shadow" trades)
            shadow = [s for s in shadow if s[0] > now]
            for _, p_s, y_s in sorted(due, key=lambda s: s[0]):
                aci.update_on_trade_close(p_s, y_s)
        if row["fold"] != fold_now:    # models were retrained for this month
            fold_now = row["fold"]
            if cusum is not None:
                cusum.reset()
            if aci is not None and fold_now in calibration:
                aci.fit_calibration(*calibration[fold_now])
        score_now = 1.0 if SCORE[version] is None else float(row[SCORE[version]])
        if aci is not None:
            score_now = float(aci.predict_lower_bound(row["p_v5s"])[0])
            shadow.append((row["label_end"], float(row["p_v5s"]), int(row[LABEL[version]])))
            if score_now < thr:
                continue
        if asset in busy_until and now < busy_until[asset]:
            continue                    # one position per market
        ctx = bandit_context(row) if bandit is not None else None
        arm = POLICIES[bandit.select(ctx) + 1] if bandit is not None else default_arm
        mult = 1.0
        if multi:
            open_risk = sum(0.01 * t["mult"] for t in open_trades)
            for t in open_trades:
                if rolling_corr is not None and t["asset"] != asset:
                    key = tuple(sorted((asset, t["asset"])))
                    c = rolling_corr[key].asof(row["time"])
                    mult *= correlation_scale(c if np.isfinite(c) else 0.0)
            mult = min(mult, max(0.0, (Q.max_portfolio_open_risk - open_risk) / 0.01))
            mult *= cusum.scale()
        if full:
            mult *= float(row["hrp_mult"]) * float(row["systemic_scale"])
        if mult < 0.1:
            continue
        p = 0.5 if PROB[version] is None else float(row[PROB[version]])
        rec = {"entry_time": now, "exit_time": row[f"exit_{arm}"], "asset": asset, "arm": arm,
               "arm_i": POLICIES.index(arm), "mult": mult, "p": p,
               "score": score_now,
               "y": int(row[LABEL[version]]), "kind": int(row["kind"]),
               **{f"r_{k}": row[f"r_{k}"] for k in POLICIES}, **{f"mae_{k}": row[f"mae_{k}"] for k in POLICIES}}
        rows.append(rec)
        busy_until[asset] = rec["exit_time"]
        open_trades.append({"exit": rec["exit_time"], "asset": asset, "mult": mult, "arm_i": rec["arm_i"],
                            "ctx": ctx, "r": row[f"r_{arm}"], "mae": row[f"mae_{arm}"], "p": p, "y": rec["y"]})
    out = to_trades(pd.DataFrame(rows))
    out.extra = {"aci": aci, "bandit": bandit, "cusum": cusum}
    return out


def to_trades(df: pd.DataFrame) -> Trades:
    if df.empty:
        z = np.zeros(0)
        return Trades(np.zeros((0, 4)), np.zeros((0, 4)), z.astype(int), z, z, z, z.astype(bool), z, z.astype(int),
                      z, df)
    df = df.sort_values("exit_time", kind="stable").reset_index(drop=True)
    day = df["exit_time"].dt.tz_convert("Europe/Prague").dt.normalize()
    gap = df["exit_time"].diff().dt.total_seconds().fillna(86_400.0).to_numpy() / 86_400.0
    return Trades(df[[f"r_{k}" for k in POLICIES]].to_numpy(float), df[[f"mae_{k}" for k in POLICIES]].to_numpy(float),
                  df["arm_i"].to_numpy(int), df["mult"].to_numpy(float), df["p"].to_numpy(float),
                  df["score"].to_numpy(float), (day != day.shift()).to_numpy(), gap, df["y"].to_numpy(int),
                  df["exit_time"].to_numpy(), df)


def rolling_correlations(returns: pd.DataFrame, window: int = 50) -> dict[tuple[str, str], pd.Series]:
    out = {}
    cols = list(returns.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            out[tuple(sorted((a, b)))] = returns[a].rolling(window).corr(returns[b])
    return out
