"""Pick the research universe point-in-time: the most traded USDT perpetuals in Dec 2024
(before the research sample starts), that also trade on spot. No hindsight in the choice."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import pandas as pd
from kenui_trader import vision as v

OUT = Path(__file__).resolve().parent / "universe.json"
STABLE = {"USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "BTCDOMUSDT", "PAXGUSDT", "USDEUSDT"}


def monthvol(sym):
    df = v._zip_csv(f"{v.BASE}/futures/um/monthly/klines/{sym}/1d/{sym}-1d-2024-12.zip")
    if df is None or not len(df):
        return sym, 0.0
    return sym, float(pd.to_numeric(df.iloc[:, 7], errors="coerce").sum())


def main(n=40):
    fut = [s for s in v.symbols("futures/um") if s.endswith("USDT") and "_" not in s and s not in STABLE]
    spot = set(v.symbols("spot"))
    with ThreadPoolExecutor(32) as ex:
        vol = dict(ex.map(monthvol, fut))
    rows = []
    for s, q in sorted(vol.items(), key=lambda kv: -kv[1]):
        sp = s[4:] if s.startswith("1000") else s
        if sp in spot and q > 0:
            rows.append({"fut": s, "spot": sp, "mult": 1000 if s.startswith("1000") else 1, "dec24_quote_vol": q})
        if len(rows) >= n:
            break
    OUT.write_text(json.dumps(rows, indent=1))
    print(pd.DataFrame(rows).to_string())


if __name__ == "__main__":
    main()
