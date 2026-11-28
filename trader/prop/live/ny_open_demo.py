"""Front 3 on the demo account: measures what the New York opening breakout really costs to execute.

The history says the breakout earns 1 to 3 basis points per trade before costs and that the cost
decides everything (RESEARCH_LOG.md, Frente 3). The hourly files have no ticks, so this robot
collects the missing piece on the MetaTrader 5 demo:

  - it records the real bid and ask of the watched symbols (every change from 08:30 to 15:10 New
    York, one sample per minute the rest of the day);
  - it trades the frozen rule with the minimum lot: range = high and low from 09:00 to 10:00 New
    York; from 10:00 on, the first side the bid touches is the trade, the other side is the stop,
    and whatever is open is closed at 15:00. One trade per symbol per day;
  - every fill is written next to the price the backtest assumes, so cost = fill against reference.

Where the server does not allow trading a symbol (or without --live, or on a netting account) the
trade is simulated on the live quotes: buy at the ask, sell at the bid. It never sends an order to
an account that is not DEMO. It uses its own magic number and does not touch the trend robot.

    python -m prop.live.ny_open_demo --live --loop      # records and trades (demo)
    python -m prop.live.ny_open_demo --loop             # records and simulates, no order
    python -m prop.live.ny_open_demo --report           # what was measured so far
"""
from __future__ import annotations

import argparse
import csv
import json
import time as clock
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
NY = ZoneInfo("America/New_York")
SYMBOLS = ("US500", "XAUUSD")                         # traded (frozen before the test)
WATCH = SYMBOLS + ("US30", "USTEC", "XAGUSD")         # quotes recorded
RANGE_START, RANGE_END, EXIT = time(9, 0), time(10, 0), time(15, 0)
REC_START, REC_END = time(8, 30), time(15, 10)
MIN_RANGE_BARS = 30                                   # one-minute bars needed inside the range
MAGIC = 550056
FIELDS = ["data", "simbolo", "simulado", "lado", "topo", "fundo", "hora_entrada", "ref_entrada", "preco_entrada",
          "spread_entrada", "hora_saida", "motivo_saida", "ref_saida", "preco_saida", "spread_saida", "custo_entrada_pb",
          "custo_saida_pb", "bruto_pb", "liquido_pb"]


def default_folder() -> Path:
    shared = ROOT.parent.parent.parent / "mt5data"    # ...\Projetos\mt5data, next to the repository
    return (shared if shared.exists() else ROOT / "state") / "ny_open"


# ---- pure logic (tested without MetaTrader) --------------------------------------------------------
def new_day(date: str) -> dict:
    return {"data": date, "estado": "espera", "topo": 0.0, "fundo": 0.0, "lado": 0}


def opening_range(bars: list[tuple[datetime, float, float]], date, now: datetime) -> tuple[float, float, bool] | None:
    """Range of the day from one-minute bars (New York start time, high, low). Returns top, bottom and
    whether a finished bar after the range already touched a side (the entry was missed)."""
    today = [b for b in bars if b[0].date() == date]
    rng = [b for b in today if RANGE_START <= b[0].time() < RANGE_END]
    if len(rng) < MIN_RANGE_BARS:
        return None
    top, bottom = max(b[1] for b in rng), min(b[2] for b in rng)
    if top <= bottom:
        return None
    later = [b for b in today if b[0].time() >= RANGE_END and b[0] + timedelta(minutes=1) <= now]
    return top, bottom, any(b[1] >= top or b[2] <= bottom for b in later)


def decide(d: dict, t: time, bid: float) -> str | None:
    """What to do now: 'compra', 'venda', 'sair:stop', 'sair:hora', 'fim' or nothing. Triggers look at the
    bid, like the bars of the backtest."""
    if d["estado"] == "armado":
        if t >= EXIT:
            return "fim"
        if bid >= d["topo"]:
            return "compra"
        if bid <= d["fundo"]:
            return "venda"
    elif d["estado"] == "aberto":
        if t >= EXIT:
            return "sair:hora"
        if (d["lado"] == 1 and bid <= d["fundo"]) or (d["lado"] == -1 and bid >= d["topo"]):
            return "sair:stop"
    return None


def side_cost(buying: bool, ref: float, fill: float) -> float:
    """Cost of one side in basis points: how much worse the fill was than the backtest's price."""
    return 1e4 * (fill - ref) / ref * (1.0 if buying else -1.0)


def close_row(d: dict, reason: str, ref: float, fill: float, spread: float, when: str) -> dict:
    side = d["lado"]
    row = {**{k: d.get(k, "") for k in FIELDS}, "hora_saida": when, "motivo_saida": reason, "ref_saida": ref,
           "preco_saida": fill, "spread_saida": spread}
    row["custo_entrada_pb"] = round(side_cost(side == 1, d["ref_entrada"], d["preco_entrada"]), 3)
    row["custo_saida_pb"] = round(side_cost(side == -1, ref, fill), 3)
    row["bruto_pb"] = round(1e4 * side * (ref / d["ref_entrada"] - 1.0), 3)
    row["liquido_pb"] = round(1e4 * side * (fill / d["preco_entrada"] - 1.0), 3)
    return row


def report(folder: Path) -> str:
    import pandas as pd
    f = folder / "trades.csv"
    if not f.exists():
        return "ainda nao ha trades gravados"
    t = pd.read_csv(f)
    t = t[t["motivo_saida"].isin(["stop", "hora"])]
    rows = []
    for sym, g in t.groupby("simbolo"):
        mid = (g["ref_entrada"] + g["ref_saida"]) / 2
        rows.append({"simbolo": sym, "trades": len(g), "simulados": int(g["simulado"].sum()),
                     "spread na entrada (pb, mediana)": round(float((1e4 * g["spread_entrada"] / mid).median()), 2),
                     "custo de entrada (pb, media)": round(float(g["custo_entrada_pb"].mean()), 2),
                     "custo de saida (pb, media)": round(float(g["custo_saida_pb"].mean()), 2),
                     "ida e volta (pb, media)": round(float((g["custo_entrada_pb"] + g["custo_saida_pb"]).mean()), 2),
                     "bruto por trade (pb)": round(float(g["bruto_pb"].mean()), 2),
                     "liquido por trade (pb)": round(float(g["liquido_pb"].mean()), 2),
                     "acerto liquido %": round(100 * float((g["liquido_pb"] > 0).mean()), 1)})
    return pd.DataFrame(rows).to_string(index=False) if rows else "ainda nao ha trades completos"


# ---- MetaTrader side ----------------------------------------------------------------------------------
class Robot:
    def __init__(self, folder: Path, live: bool) -> None:
        import MetaTrader5 as mt5
        self.mt5, self.folder = mt5, folder
        if not mt5.initialize():
            raise SystemExit(f"nao consegui falar com o MetaTrader 5 (abra o terminal e entre na conta): {mt5.last_error()}")
        acc = mt5.account_info()
        if acc is None:
            raise SystemExit("o terminal esta aberto mas sem conta conectada")
        self.demo = acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
        self.hedging = acc.margin_mode == mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING
        self.live = live and self.demo
        (folder / "ticks").mkdir(parents=True, exist_ok=True)
        self.state_file = folder / "state.json"
        self.days: dict = json.loads(self.state_file.read_text()) if self.state_file.exists() else {}
        self.seen: dict = {}                              # symbol -> (last tick time in ms, when it changed, written minute)
        self.offset: int | None = None                    # server clock minus UTC, in seconds
        self.changed_at = 0.0
        self.last_status = 0.0
        for s in WATCH:
            mt5.symbol_select(s, True)
        print(f"conta {'DEMO' if self.demo else 'REAL'} em {acc.server} | pasta {folder}")
        for s in SYMBOLS:
            print(f"  {s}: {'ordens de lote minimo na demo' if self.real(s) else 'simulado nas cotacoes ao vivo'}")
        if live and not self.demo:
            print("  esta conta nao e demo: nenhuma ordem sera enviada, so gravo e simulo")

    def real(self, sym: str) -> bool:
        info = self.mt5.symbol_info(sym)
        return bool(self.live and self.hedging and info is not None and info.trade_mode == self.mt5.SYMBOL_TRADE_MODE_FULL)

    def save(self) -> None:
        self.state_file.write_text(json.dumps(self.days))

    def journal(self, row: dict) -> None:
        f = self.folder / "trades.csv"
        fresh = not f.exists()
        with f.open("a", newline="") as h:
            w = csv.DictWriter(h, fieldnames=FIELDS)
            if fresh:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in FIELDS})

    def record(self, sym: str, tick, now_ny: datetime) -> None:
        last = self.seen.get(sym)
        if last is None:                                  # the first reading may be an old quote of a closed market
            self.seen[sym] = (tick.time_msc, "")
            return
        if tick.time_msc == last[0]:
            return
        self.changed_at = clock.monotonic()
        self.offset = round((tick.time - datetime.now(timezone.utc).timestamp()) / 1800) * 1800
        minute = now_ny.strftime("%H:%M")
        if REC_START <= now_ny.time() < REC_END or minute != last[1]:
            f = self.folder / "ticks" / f"{sym}_{now_ny:%Y-%m-%d}.csv"
            fresh = not f.exists()
            with f.open("a") as h:
                h.write(("hora_ny,tempo_ms_servidor,bid,ask\n" if fresh else "") + f"{now_ny:%H:%M:%S},{tick.time_msc},{tick.bid},{tick.ask}\n")
            last = (last[0], minute)
        self.seen[sym] = (tick.time_msc, last[1])

    def minute_bars(self, sym: str) -> list[tuple[datetime, float, float]]:
        r = self.mt5.copy_rates_from_pos(sym, self.mt5.TIMEFRAME_M1, 0, 600)
        if r is None or self.offset is None:
            return []
        return [(datetime.fromtimestamp(int(b["time"]) - self.offset, timezone.utc).astimezone(NY), float(b["high"]), float(b["low"]))
                for b in r]

    def held(self, sym: str) -> list:
        return [p for p in (self.mt5.positions_get(symbol=sym) or []) if p.magic == MAGIC]

    def send(self, sym: str, buy: bool, tick, sl: float = 0.0, position=None) -> float | None:
        """Sends a market order of the minimum lot (or closes `position`). Returns the fill price."""
        mt5 = self.mt5
        info = mt5.symbol_info(sym)
        fill = mt5.ORDER_FILLING_FOK if info.filling_mode & 1 else (mt5.ORDER_FILLING_IOC if info.filling_mode & 2 else mt5.ORDER_FILLING_RETURN)
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": float(position.volume if position else info.volume_min),
               "magic": MAGIC, "deviation": 100, "type": mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL,
               "price": tick.ask if buy else tick.bid, "type_filling": fill, "type_time": mt5.ORDER_TIME_GTC, "comment": "kenui-ny"}
        if sl > 0:
            req["sl"] = round(sl, info.digits)
        if position is not None:
            req["position"] = position.ticket
        res = mt5.order_send(req)
        if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"  {sym}: ordem recusada ({mt5.last_error() if res is None else f'{res.retcode} {res.comment}'})", flush=True)
            return None
        return float(res.price) if res.price else float(tick.ask if buy else tick.bid)

    def handle(self, sym: str, tick, now_ny: datetime) -> None:
        date, hm = f"{now_ny:%Y-%m-%d}", f"{now_ny:%H:%M:%S}"
        d = self.days.get(sym)
        if d is None or d["data"] != date:
            if d is not None and d["estado"] == "aberto":     # the computer was off at the exit hour
                self.exit(sym, d, "atrasado", tick, tick.bid if d["lado"] == 1 else tick.ask, hm)
            d = self.days[sym] = new_day(date)
            self.save()
        if d["estado"] == "espera" and now_ny.time() >= RANGE_END:
            r = opening_range(self.minute_bars(sym), now_ny.date(), now_ny) if now_ny.time() < EXIT else None
            if r is None or r[2]:
                d["estado"] = "fim"
                print(f"  {sym}: sem trade hoje ({'faixa de abertura incompleta' if r is None else 'o rompimento aconteceu antes de eu ligar'})", flush=True)
            else:
                d.update(estado="armado", topo=r[0], fundo=r[1])
                print(f"  {sym}: faixa de abertura {r[1]:.2f} a {r[0]:.2f}, esperando o rompimento ate 15:00 de NY", flush=True)
            self.save()
        if d["estado"] == "aberto" and d["real"] and not self.held(sym):
            self.exit(sym, d, "fechado fora do robo", tick, tick.bid, hm, send=False)
            return
        act = decide(d, now_ny.time(), tick.bid)
        if act == "fim":
            d["estado"] = "fim"
            print(f"  {sym}: o preco ficou dentro da faixa, sem trade hoje", flush=True)
            self.save()
        elif act in ("compra", "venda"):
            buy, real = act == "compra", self.real(sym)
            ref = d["topo"] if buy else d["fundo"]
            width = d["topo"] - d["fundo"]
            price = (self.send(sym, buy, tick, sl=(d["fundo"] - width) if buy else (d["topo"] + width)) if real
                     else (tick.ask if buy else tick.bid))
            if price is None:
                d["estado"] = "fim"
            else:
                d.update(estado="aberto", lado=1 if buy else -1, real=real, simulado=int(not real), simbolo=sym, hora_entrada=hm,
                         ref_entrada=ref, preco_entrada=price, spread_entrada=round(tick.ask - tick.bid, 6))
                print(f"  {sym}: {act}{'' if real else ' simulada'} a {price:.2f} (referencia {ref:.2f}, spread {tick.ask - tick.bid:.2f})", flush=True)
            self.save()
        elif act in ("sair:stop", "sair:hora"):
            ref = (d["fundo"] if d["lado"] == 1 else d["topo"]) if act == "sair:stop" else tick.bid
            self.exit(sym, d, act.split(":")[1], tick, ref, hm)

    def exit(self, sym: str, d: dict, reason: str, tick, ref: float, hm: str, send: bool = True) -> None:
        price = tick.bid if d["lado"] == 1 else tick.ask
        if d.get("real") and send:
            for p in self.held(sym):
                price = self.send(sym, d["lado"] == -1, tick, position=p) or price
        row = close_row(d, reason, ref, price, round(tick.ask - tick.bid, 6), hm)
        self.journal(row)
        d["estado"] = "fim"
        self.save()
        print(f"  {sym}: saida ({reason}) a {price:.2f}, resultado liquido {row['liquido_pb']:+.1f} pb, "
              f"custo de ida e volta {row['custo_entrada_pb'] + row['custo_saida_pb']:.1f} pb", flush=True)

    def step(self) -> None:
        now_ny = datetime.now(NY)
        ticks = {s: self.mt5.symbol_info_tick(s) for s in WATCH}
        for s, t in ticks.items():
            if t is not None and t.ask > 0:
                self.record(s, t, now_ny)
        open_market = self.offset is not None and clock.monotonic() - self.changed_at < 120
        if open_market:
            for s in SYMBOLS:
                t = ticks[s]
                if t is not None and t.ask > 0 and abs(t.time - self.offset - datetime.now(timezone.utc).timestamp()) < 120:
                    self.handle(s, t, now_ny)
        if clock.monotonic() - self.last_status >= 300:
            self.last_status = clock.monotonic()
            what = "  ".join(f"{s} {self.days[s]['estado']}" for s in SYMBOLS if s in self.days) or "aguardando as 10:00 de NY"
            print(f"{now_ny:%Y-%m-%d %H:%M} NY  {'gravando cotacoes' if open_market else 'mercado fechado, aguardando'}  {what}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Frente 3 na demo: grava cotacoes e mede o custo do rompimento da abertura de NY")
    ap.add_argument("--live", action="store_true", help="envia ordens de lote minimo (so em conta demo)")
    ap.add_argument("--loop", action="store_true", help="continua rodando")
    ap.add_argument("--report", action="store_true", help="mostra o que foi medido ate agora")
    ap.add_argument("--pasta", default=None, help="onde gravar (padrao: mt5data\\ny_open)")
    a = ap.parse_args()
    folder = Path(a.pasta) if a.pasta else default_folder()
    if a.report:
        return print(report(folder))
    r = Robot(folder, a.live)
    while True:
        r.step()
        if not a.loop:
            break
        clock.sleep(1)


if __name__ == "__main__":
    main()
