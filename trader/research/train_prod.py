"""Train the production model (1-hour forecast) on ALL data available, and save it for the bot."""
from __future__ import annotations

import gc
import json
from pathlib import Path

import lightgbm as lgb

from research import dataset as DS
from research.ml import DROP, PARAMS, ROUNDS

MODELS = Path(__file__).resolve().parent.parent / "models"


def main(step=4):
    big = DS.load()
    feats = [c for c in big.columns if c not in DROP]
    tr = big.iloc[::step]
    tr = tr[tr["fwd_1h"].notna()]
    last = tr.index.max()
    y = tr["fwd_1h"].astype("float64")
    scale = float(y.std())
    y = (y / scale).clip(-5, 5)
    ds = lgb.Dataset(tr[feats].to_numpy(dtype="float32"), y.to_numpy(), feature_name=feats)
    ds.construct()
    del big, tr, y
    gc.collect()
    model = lgb.train(PARAMS, ds, ROUNDS)
    MODELS.mkdir(exist_ok=True)
    model.save_model(str(MODELS / "pred_1h.txt"))
    (MODELS / "pred_1h.json").write_text(json.dumps({"features": feats, "scale": scale, "trained_until": str(last)}, indent=1))
    print("saved", MODELS / "pred_1h.txt", "trained until", last, "features", len(feats))


if __name__ == "__main__":
    main()
