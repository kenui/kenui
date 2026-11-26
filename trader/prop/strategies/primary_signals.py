"""Primary signals (V2+): high-sensitivity candidates from both engines. They are meant to
catch every opportunity; the meta-model decides which ones are worth trading."""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.strategies.indicators import atr, bb_width, bollinger, rsi

BREAKOUT, REVERSION = 1, 2


def generate(df: pd.DataFrame, channel: int = 20, bb_n: int = 20, bb_k: float = 2.0,
             rsi_low: float = 35.0) -> pd.DataFrame:
    """Columns: side (+1/-1/0), kind (1 breakout, 2 reversion), atr.

    Breakout: close beyond the previous `channel`-bar high/low after the band width was below
    its 10-day median within the last 8 bars. Reversion: close outside the Bollinger band with
    RSI stretched. Breakout wins when both fire.
    """
    c = df["close"]
    w = bb_width(c, 20)
    squeezed = (w < w.rolling(240).median()).shift(1).rolling(8).max().fillna(0).astype(bool)
    hi, lo = df["high"].rolling(channel).max().shift(1), df["low"].rolling(channel).min().shift(1)
    bo = np.where(squeezed & (c > hi), 1, np.where(squeezed & (c < lo), -1, 0))
    _, up, dn = bollinger(c, bb_n, bb_k)
    r = rsi(c, 14)
    mr = np.where((c < dn) & (r < rsi_low), 1, np.where((c > up) & (r > 100 - rsi_low), -1, 0))
    side = np.where(bo != 0, bo, mr)
    kind = np.where(bo != 0, BREAKOUT, np.where(mr != 0, REVERSION, 0))
    return pd.DataFrame({"side": side.astype(np.int8), "kind": kind.astype(np.int8), "atr": atr(df, 14)},
                        index=df.index)
