"""Exports daily and hourly bars of the markets the MetaTrader 5 server offers and that are not in the folder yet.

    python -m prop.data.mt5_export C:\\Users\\kenui\\Projetos\\mt5data            # everything except single stocks
    python -m prop.data.mt5_export C:\\Users\\kenui\\Projetos\\mt5data --lista    # only writes the list of symbols
    python -m prop.data.mt5_export C:\\Users\\kenui\\Projetos\\mt5data --fundos   # the exchange-traded funds in FUNDS

Writes <SYMBOL>_D1.csv.gz and <SYMBOL>_H1.csv.gz in the format mt5_study reads, adds the new symbols to
symbols.json and writes servidor_simbolos.csv with every symbol of the server (name, group path,
description, whether it can be traded). It only reads: no order is sent.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

SKIP = ("stock", "share", "equit", "etf", "acoes")          # group paths left out unless --tudo
SPEC = ["path", "digits", "point", "spread", "trade_contract_size", "trade_tick_size", "trade_tick_value", "volume_min",
        "volume_step", "swap_long", "swap_short", "swap_mode", "swap_rollover3days", "trade_mode", "bid", "ask"]
MAX_NEW = 200
# Exchange-traded funds that stand for markets the server has no contract for: oil, gas, bonds, broad commodities,
# volatility, bitcoin, countries and US sectors. Daily history of these is the closest thing to those markets here.
FUNDS = ["USO", "BNO", "UNG", "DBC", "DBA", "CPER", "GLD", "SLV", "PPLT", "TLT", "IEF", "SHY", "TIP", "LQD", "HYG", "EMB",
         "UUP", "FXE", "FXY", "SPY", "QQQ", "IWM", "DIA", "EFA", "EEM", "EWJ", "EWZ", "FXI", "INDA", "EWG", "EWU", "VNQ",
         "XLE", "XLF", "XLK", "XLV", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE", "XLC", "VIXY", "SVXY", "IBIT", "BITO", "ETHA",
         "GDX", "KRE", "SMH", "XBI", "ARKK"]


def wanted(path: str, everything: bool) -> bool:
    return everything or not any(k in path.lower() for k in SKIP)


def main() -> None:
    import MetaTrader5 as mt5
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    folder = Path(args[0]) if args else Path("data/mt5")
    folder.mkdir(parents=True, exist_ok=True)
    if not mt5.initialize():
        raise SystemExit(f"nao consegui falar com o MetaTrader 5 (abra o terminal e entre na conta): {mt5.last_error()}")
    syms = mt5.symbols_get() or []
    pd.DataFrame([{"simbolo": s.name, "grupo": s.path, "descricao": s.description, "negociavel": int(s.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL)}
                  for s in syms]).to_csv(folder / "servidor_simbolos.csv", index=False)
    print(f"{len(syms)} simbolos no servidor, lista em {folder / 'servidor_simbolos.csv'}")
    if "--lista" in sys.argv:
        return
    spec_file = folder / "symbols.json"
    spec = json.loads(spec_file.read_text()) if spec_file.exists() else {}
    if "--fundos" in sys.argv:
        new = [s for s in syms if s.name in FUNDS and not (folder / f"{s.name}_D1.csv.gz").exists()]
    else:
        new = [s for s in syms if wanted(s.path, "--tudo" in sys.argv) and not (folder / f"{s.name}_D1.csv.gz").exists()][:MAX_NEW]
    done = 0
    print(f"{len(new)} mercados para exportar; os que ainda nao estao no terminal levam alguns segundos cada", flush=True)
    for s in new:
        mt5.symbol_select(s.name, True)
        for _ in range(20):                                       # a newly selected symbol downloads its history in the background
            r = mt5.copy_rates_from_pos(s.name, mt5.TIMEFRAME_D1, 0, 400)
            if r is not None and len(r) > 300:
                break
            time.sleep(0.5)
        got = {}
        for tf, code in (("D1", mt5.TIMEFRAME_D1), ("H1", mt5.TIMEFRAME_H1)):
            r = None
            for n in (99999, 50000, 20000, 5000):                 # the terminal limits how many bars one call returns
                r = mt5.copy_rates_from_pos(s.name, code, 0, n)
                if r is not None and len(r):
                    break
            if r is not None and len(r) > 300:
                got[tf] = pd.DataFrame(r)
        if "D1" not in got:
            print(f"  {s.name}: sem historico suficiente", flush=True)
            continue
        for tf, df in got.items():
            df.to_csv(folder / f"{s.name}_{tf}.csv.gz", index=False, compression="gzip")
        info = mt5.symbol_info(s.name)
        spec[s.name] = {k: getattr(info, k) for k in SPEC if hasattr(info, k)}
        spec_file.write_text(json.dumps(spec))                    # saved at each market, so stopping midway loses nothing
        done += 1
        print(f"  {s.name}: {len(got['D1'])} dias" + (f", {len(got['H1'])} horas" if "H1" in got else ""), flush=True)
    spec_file.write_text(json.dumps(spec))
    print(f"pronto: {done} mercados novos em {folder}")


if __name__ == "__main__":
    main()
