"""Read-only snapshots of Uniswap-v3-style pools on Base from a public archive RPC.

One Multicall3 eth_call per snapshot returns slot0, liquidity and both
feeGrowthGlobal counters at a historical block. feeGrowthGlobal is the exact
amount of fees paid per unit of in-range liquidity, so no volume/TVL guessing.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import requests
from eth_abi import decode, encode

RPC = os.environ.get("BASE_RPC", "https://mainnet.base.org")
MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"
BASE_GENESIS_TS = 1686789347  # block 0; Base produces one block every 2 s
SEL = {
    "slot0": "3850c7bd",
    "liquidity": "1a686502",
    "fg0": "f3058399",
    "fg1": "46141319",
}
DATA_DIR = Path(os.environ.get("KENUI_DEFI_DATA", Path(__file__).resolve().parents[1] / "data" / "defi"))


def block_ts(block: int) -> int:
    return BASE_GENESIS_TS + 2 * block


def ts_block(ts: int) -> int:
    return (ts - BASE_GENESIS_TS) // 2


def _calldata(pool: str, extra: list[tuple[str, str]] | None = None) -> str:
    calls = [(pool, True, bytes.fromhex(s)) for s in SEL.values()]
    for addr, sel in extra or []:
        calls.append((addr, True, bytes.fromhex(sel)))
    # aggregate3((address,bool,bytes)[]) -> (bool,bytes)[]
    return "0x82ad56cb" + encode(["(address,bool,bytes)[]"], [calls]).hex()


def _decode(result_hex: str, n_extra: int = 0) -> dict:
    (res,) = decode(["(bool,bytes)[]"], bytes.fromhex(result_hex[2:]))
    out = {}
    ok, raw = res[0]
    out["sqrtPriceX96"] = int.from_bytes(raw[0:32], "big") if ok and len(raw) >= 64 else 0
    out["tick"] = int.from_bytes(raw[32:64], "big", signed=True) if ok and len(raw) >= 64 else 0
    for i, k in enumerate(["liquidity", "fg0", "fg1"], start=1):
        ok, raw = res[i]
        out[k] = int.from_bytes(raw[:32], "big") if ok and len(raw) >= 32 else 0
    for j in range(n_extra):
        ok, raw = res[4 + j]
        out[f"x{j}"] = int.from_bytes(raw[:32], "big") if ok and len(raw) >= 32 else 0
    return out


def fetch_snapshots(pool: str, blocks: list[int], extra=None, batch: int = 20,
                    pause: float = 0.12, session: requests.Session | None = None) -> pd.DataFrame:
    s = session or requests.Session()
    data = _calldata(pool, extra)
    n_extra = len(extra or [])
    rows: dict[int, dict] = {}
    todo = list(blocks)
    delay = pause
    while todo:
        chunk, todo = todo[:batch], todo[batch:]
        payload = [{"jsonrpc": "2.0", "id": b, "method": "eth_call",
                    "params": [{"to": MULTICALL3, "data": data}, hex(b)]} for b in chunk]
        try:
            r = s.post(RPC, json=payload, timeout=60)
            js = r.json()
            if not isinstance(js, list):
                js = []
        except Exception:
            js = []
        got = set()
        for item in js:
            if "result" in item and len(item["result"]) > 2:
                try:
                    rows[item["id"]] = _decode(item["result"], n_extra)
                    got.add(item["id"])
                except Exception:
                    pass
        missed = [b for b in chunk if b not in got]
        if missed:
            todo = missed + todo
            delay = min(delay * 1.5 + 0.05, 5.0)
        else:
            delay = max(pause, delay * 0.9)
        time.sleep(delay)
    df = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    df.index.name = "block"
    return df


def download_pool(name: str, pool: str, start_ts: int, end_ts: int, step_s: int = 300,
                  extra=None, chunk: int = 2000, verbose: bool = True) -> Path:
    """Snapshot a pool every step_s seconds; resumable, stored as pickled DataFrame of Python ints."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{name}.pkl"
    have = pd.read_pickle(path) if path.exists() else None
    blocks = list(range(ts_block(start_ts), ts_block(end_ts), step_s // 2))
    if have is not None:
        done = set(have.index)
        blocks = [b for b in blocks if b not in done]
    s = requests.Session()
    t0 = time.time()
    for i in range(0, len(blocks), chunk):
        part = fetch_snapshots(pool, blocks[i:i + chunk], extra=extra, session=s)
        have = part if have is None else pd.concat([have, part]).sort_index()
        have.to_pickle(path)
        if verbose:
            print(f"{name}: {i + len(part)}/{len(blocks)} new snapshots, {time.time() - t0:.0f}s", flush=True)
    return path
