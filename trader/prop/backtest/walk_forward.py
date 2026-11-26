"""Purged walk-forward validation.

For every test month: fit the HMM, the fractional-differentiation order, the HRP weights and
all meta-models on the previous `train_months` only, drop training events whose label window
reaches into the test month (purge) plus `max_holding_bars` hours before it (embargo), then
predict the test month. Nothing fitted ever sees its own test data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.config.quant import Q
from prop.config.settings import INSTRUMENTS
from prop.data.multi_asset_loader import aligned_returns
from prop.features.engineering import base_features
from prop.features.fractional_and_physics import SIGNATURE, choose_d, ffd_table, physics_features, signature_features
from prop.features.microstructure_features import micro_features
from prop.labeling.triple_barrier import label_events
from prop.labeling.triple_barrier_mae import add_labels
from prop.models import regime_hmm
from prop.models.calibrated_meta_labeler import CalibratedMetaLabeler
from prop.models.conformal_meta_ensemble import ConformalMetaEnsemble
from prop.models.meta_labeler import MetaLabeler
from prop.portfolio import hrp_systemic_risk as hrp
from prop.strategies import primary_signals

BASE = ["ret_1", "ret_3", "ret_5", "ret_12", "ret_24", "vol_yz", "vol_ratio", "atr_pct", "z_20", "z_50",
        "bb_width", "bb_width_rel", "rel_volume", "rsi", "hour_sin", "hour_cos"]
MICRO = ["amihud", "amihud_pct", "vpin", "vpin_pct", "flow_signed", "spread_spike"]
PHYSICS = ["hurst", "ou_tau_feat", "ffd"]
HMM = list(regime_hmm.STATES)
FEATS_V2 = BASE + HMM + ["side", "kind", "asset_id"]
FEATS_V4 = FEATS_V2 + MICRO
FEATS_V5 = FEATS_V4 + PHYSICS
FEATS_V5S = FEATS_V5 + SIGNATURE.columns


def build_events(fast: dict[str, pd.DataFrame], slow: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict]:
    """Event table (one row per primary signal, all assets) and per-asset context series."""
    frames, ctx = [], {}
    for i, (asset, bars) in enumerate(slow.items()):
        feats = pd.concat([base_features(bars), micro_features(bars), physics_features(bars),
                           signature_features(bars)], axis=1)
        ev = add_labels(label_events(fast[asset], primary_signals.generate(bars), INSTRUMENTS[asset]))
        ev = ev.join(feats, how="left")
        ev["asset"], ev["asset_id"] = asset, i
        frames.append(ev)
        ctx[asset] = {"obs": regime_hmm.observations(bars), "ffd": ffd_table(np.log(bars["close"]))}
    events = pd.concat(frames).sort_values("entry_time", kind="stable")
    events.index.name = "time"
    return events.reset_index(), ctx


def month_starts(events: pd.DataFrame) -> list[pd.Timestamp]:
    first = events["time"].min().normalize().replace(day=1) + pd.DateOffset(months=Q.train_months + 1)
    return list(pd.date_range(first, events["time"].max(), freq="MS", tz="UTC"))


def add_fold_features(events: pd.DataFrame, ctx: dict, train_mask_bars, seed: int) -> pd.DataFrame:
    """Attach HMM probabilities and the fractionally differentiated price, both fitted on the
    training bars selected by `train_mask_bars(index) -> bool array`."""
    ev = events.copy()
    for col in HMM + ["ffd"]:
        ev[col] = np.nan
    for asset, c in ctx.items():
        rows = ev["asset"] == asset
        if not rows.any():
            continue
        obs = c["obs"]
        tr = train_mask_bars(obs.index)
        if tr.sum() < 300:
            continue
        seg = np.flatnonzero(np.diff(np.r_[0, tr.astype(int), 0]))  # run boundaries of the train bars
        lengths = (seg[1::2] - seg[0::2]).tolist()
        model = regime_hmm.RegimeHMM(seed=seed).fit(obs[tr], lengths)
        probs = model.filtered(obs)
        ev.loc[rows, HMM] = probs.reindex(ev.loc[rows, "time"]).to_numpy()
        table = c["ffd"]
        d = choose_d(table, obs.index[tr])
        col = table[d]
        mu, sd = col[train_mask_bars(col.index)].mean(), col[train_mask_bars(col.index)].std()
        ev.loc[rows, "ffd"] = ((col - mu) / (sd + 1e-12)).reindex(ev.loc[rows, "time"]).to_numpy()
    return ev


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, seed: int, versions: tuple[str, ...],
                calibration: dict | None = None, key: int = 0) -> pd.DataFrame:
    """Fit every requested meta-model on `train` (time ordered) and predict `test`.
    For "v5s" the calibration scores of the fold are stored in `calibration[key]`, because the
    adaptive conformal bound is applied later, trade by trade, in time order."""
    out = pd.DataFrame(index=test.index)
    med = train[FEATS_V5S].median()

    def mat(df: pd.DataFrame, cols: list[str]) -> np.ndarray:
        return df[cols].fillna(med[cols]).fillna(0.0).to_numpy(float)

    if "v2" in versions:
        out["p_v2"] = MetaLabeler(seed).fit(mat(train, FEATS_V2), train["y_v2"].to_numpy()).predict_proba(mat(test, FEATS_V2))
    if "v3" in versions:
        out["p_v3"] = CalibratedMetaLabeler(seed).fit(mat(train, FEATS_V2), train["y_v3"].to_numpy()).predict_proba(mat(test, FEATS_V2))
    for tag, cols in (("v4", FEATS_V4), ("v5", FEATS_V5)):
        if tag in versions:
            ens = ConformalMetaEnsemble(seed=seed).fit(mat(train, cols), train["y_v4"].to_numpy(),
                                                       train["w_v4"].to_numpy(), purge=Q.max_holding_bars)
            out[f"p_{tag}"], out[f"plo_{tag}"], out[f"pup_{tag}"] = ens.predict(mat(test, cols))
    if "v5s" in versions:
        ens = ConformalMetaEnsemble(seed=seed, adaptive=True).fit(
            mat(train, FEATS_V5S), train["y_v4"].to_numpy(), train["w_v4"].to_numpy(), purge=Q.max_holding_bars)
        out["p_v5s"] = ens.predict(mat(test, FEATS_V5S))[0]
        if calibration is not None:
            calibration[key] = (ens.cal_p.copy(), ens.cal_y.copy())
    return out


def run(events: pd.DataFrame, ctx: dict, slow: dict[str, pd.DataFrame],
        versions: tuple[str, ...] = ("v2", "v3", "v4", "v5", "v5s"), verbose: bool = True) -> pd.DataFrame:
    """Out-of-sample event table: every test-month event with the predictions made for it.
    `result.attrs["calibration"]` holds the per-fold calibration scores of the adaptive model."""
    calibration: dict = {}
    rets = aligned_returns(slow)
    embargo = pd.Timedelta(Q.timeframe) * Q.max_holding_bars
    parts = []
    for k, ts in enumerate(month_starts(events)):
        te, tr0 = ts + pd.DateOffset(months=Q.test_months), ts - pd.DateOffset(months=Q.train_months)
        in_train = (events["time"] >= tr0) & (events["label_end"] <= ts) & (events["time"] < ts - embargo)
        in_test = (events["time"] >= ts) & (events["time"] < te)
        if in_train.sum() < 200 or not in_test.any():
            continue
        ev = add_fold_features(events[in_train | in_test], ctx, lambda idx: (idx >= tr0) & (idx < ts), seed=k)
        train, test = ev[in_train[ev.index]], ev[in_test[ev.index]]
        pred = fit_predict(train, test, k, versions, calibration, k)
        fold = pd.concat([test, pred], axis=1)
        mult = hrp.risk_multipliers(rets[(rets.index >= tr0) & (rets.index < ts)])
        fold["hrp_mult"] = fold["asset"].map(mult).to_numpy()
        fold["fold"] = k
        parts.append(fold)
        if verbose:
            print(f"  janela {k:2d}: teste {ts:%Y-%m}  treino {len(train):4d} eventos  teste {len(test):3d}", flush=True)
    oos = pd.concat(parts).sort_values("entry_time", kind="stable").reset_index(drop=True)
    ar = hrp.systemic_scale(hrp.absorption_ratio(rets))
    oos["systemic_scale"] = ar.reindex(oos["time"]).to_numpy()
    oos.attrs["calibration"] = calibration
    return oos
