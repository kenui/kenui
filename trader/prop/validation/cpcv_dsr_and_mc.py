"""V5 validation: is the result real or the best of many tries?

deflated_sharpe  Deflated Sharpe Ratio (Bailey and Lopez de Prado): probability that the true
                 Sharpe is above zero after discounting the number of variants tried, the
                 sample length and the skew and fat tails of the daily results.
pbo_cscv         Probability of Backtest Overfitting by combinatorially symmetric
                 cross-validation: how often the variant that looks best on half of the days
                 lands in the bottom half on the other days.
cpcv             Combinatorial purged cross-validation: 6 time groups, 2 held out at a time
                 (15 fits, 5 complete out-of-sample paths), with purge and embargo.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

from prop.backtest import walk_forward as wf
from prop.config.quant import Q
from prop.data.multi_asset_loader import aligned_returns
from prop.portfolio import hrp_systemic_risk as hrp

EULER = 0.5772156649015329


def sharpe(daily: np.ndarray) -> float:
    """Per-period (not annualised) Sharpe ratio."""
    sd = np.std(daily, ddof=1) if len(daily) > 1 else 0.0
    return float(np.mean(daily) / sd) if sd > 0 else 0.0


def expected_max_sharpe(n_trials: int, var_trials: float) -> float:
    """Sharpe the best of `n_trials` unskilled variants is expected to show by luck alone."""
    if n_trials < 2 or var_trials <= 0:
        return 0.0
    return float(np.sqrt(var_trials) * ((1 - EULER) * norm.ppf(1 - 1 / n_trials)
                                        + EULER * norm.ppf(1 - 1 / (n_trials * np.e))))


def deflated_sharpe(daily: np.ndarray, n_trials: int, var_trials: float) -> float:
    """Probability (0 to 1) that the Sharpe of `daily` beats the luck benchmark."""
    daily = np.asarray(daily, float)
    t = len(daily)
    if t < 30 or np.std(daily) == 0:
        return 0.0
    sr = sharpe(daily)
    sr0 = expected_max_sharpe(n_trials, var_trials)
    g3, g4 = float(skew(daily)), float(kurtosis(daily, fisher=False))
    denom = np.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    return float(norm.cdf((sr - sr0) * np.sqrt(t - 1) / denom))


def pbo_cscv(matrix: np.ndarray, blocks: int = 10) -> dict:
    """`matrix`: rows = days, columns = variants (daily results)."""
    m = np.asarray(matrix, float)
    m = m[:, m.std(axis=0) > 0]
    t, n = m.shape
    if n < 4 or t < blocks * 5:
        return {"pbo": float("nan"), "variants": n, "splits": 0, "oos_loss_prob": float("nan")}
    parts = np.array_split(np.arange(t), blocks)
    logits, oos_best = [], []
    for combo in combinations(range(blocks), blocks // 2):
        ins = np.concatenate([parts[i] for i in combo])
        out = np.concatenate([parts[i] for i in range(blocks) if i not in combo])
        sr_in = m[ins].mean(axis=0) / (m[ins].std(axis=0) + 1e-12)
        sr_out = m[out].mean(axis=0) / (m[out].std(axis=0) + 1e-12)
        best = int(np.argmax(sr_in))
        rank = (np.argsort(np.argsort(sr_out))[best] + 1) / (n + 1)      # 0..1, 1 = best out of sample
        logits.append(np.log(rank / (1 - rank)))
        oos_best.append(sr_out[best])
    logits = np.array(logits)
    return {"pbo": float((logits <= 0).mean()), "variants": n, "splits": len(logits),
            "oos_loss_prob": float((np.array(oos_best) <= 0).mean())}


def cpcv(events: pd.DataFrame, ctx: dict, slow: dict[str, pd.DataFrame], versions: tuple[str, ...] = ("v5", "v5s"),
         groups: int = 6, held_out: int = 2, verbose: bool = True) -> list[pd.DataFrame]:
    """Returns the complete out-of-sample paths (each one an event table like the walk-forward
    output, covering the whole history, predicted by models that never saw those dates)."""
    rets = aligned_returns(slow)
    embargo = pd.Timedelta(Q.timeframe) * Q.max_holding_bars
    edges = pd.date_range(events["time"].min(), events["time"].max() + pd.Timedelta(hours=1), periods=groups + 1)
    grp = np.clip(np.searchsorted(edges, events["time"], side="right") - 1, 0, groups - 1)
    ar = hrp.systemic_scale(hrp.absorption_ratio(rets))
    pieces: dict[int, list[pd.DataFrame]] = {g: [] for g in range(groups)}
    calibration: dict[int, tuple] = {}
    for s, test_groups in enumerate(combinations(range(groups), held_out)):
        in_test = np.isin(grp, test_groups)
        in_train = ~in_test
        spans = [(edges[g], edges[g + 1]) for g in test_groups]
        for lo, hi in spans:      # purge labels that reach into a test block, embargo after it
            in_train &= ~((events["label_end"] > lo - embargo) & (events["time"] < hi + embargo)).to_numpy()

        def train_bars(idx, spans=spans):
            ok = np.ones(len(idx), bool)
            for lo, hi in spans:
                ok &= ~((idx >= lo - embargo) & (idx < hi + embargo))
            return ok

        ev = wf.add_fold_features(events, ctx, train_bars, seed=s)
        train, test = ev[in_train], ev[in_test]
        pred = wf.fit_predict(train, test, s, versions, calibration, s)
        fold = pd.concat([test, pred], axis=1)
        mult = hrp.risk_multipliers(rets[train_bars(rets.index)])
        fold["hrp_mult"] = fold["asset"].map(mult).to_numpy()
        fold["fold"] = s
        fold["systemic_scale"] = ar.reindex(fold["time"]).to_numpy()
        fold["_grp"] = grp[in_test]
        for g in test_groups:
            pieces[g].append(fold[fold["_grp"] == g].drop(columns="_grp"))
        if verbose:
            print(f"  CPCV {s + 1:2d}/15: fora {test_groups}  treino {len(train)}  teste {len(test)}", flush=True)
    n_paths = min(len(v) for v in pieces.values())
    paths = []
    for k in range(n_paths):
        path = pd.concat([pieces[g][k] for g in range(groups)]).sort_values("entry_time", kind="stable").reset_index(drop=True)
        path.attrs["calibration"] = calibration
        paths.append(path)
    return paths
