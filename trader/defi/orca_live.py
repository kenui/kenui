"""Sample Orca Whirlpool state from the public Orca API (read-only).

Solana has no free archive of past pool state, so exact fee-per-liquidity can
only be measured forward in time. Usage: python -m defi.orca_live [minutes] [step_s]
"""
import json
import sys
import time

import requests

from .chain import DATA_DIR

POOLS = {
    "orca_sol_usdc_004": "Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE",
}
URL = "https://api.orca.so/v2/solana/pools/{}"
KEEP = ["liquidity", "sqrtPrice", "tickCurrentIndex", "feeGrowthGlobalA", "feeGrowthGlobalB",
        "feeRate", "protocolFeeRate", "updatedSlot", "tvlUsdc", "price"]

if __name__ == "__main__":
    minutes = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    step = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    end = time.time() + minutes * 60
    while time.time() < end:
        for name, addr in POOLS.items():
            try:
                d = requests.get(URL.format(addr), timeout=20).json()["data"]
                row = {k: d.get(k) for k in KEEP}
                row["ts"] = time.time()
                with open(DATA_DIR / f"{name}_live.jsonl", "a") as f:
                    f.write(json.dumps(row) + "\n")
            except Exception as e:  # keep sampling
                print("err", e, flush=True)
        time.sleep(step - time.time() % step)
