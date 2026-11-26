//+------------------------------------------------------------------+
//| PropGuardV5_Executor.mq5                                         |
//| Executor and tick-by-tick guardian for the Python brain          |
//| (prop/execution/mt5_socket_bridge.py).                           |
//|                                                                  |
//| - connects as a TCP client to the Python bridge on 127.0.0.1     |
//|   (add 127.0.0.1 in Tools > Options > Expert Advisors > WebRequest)|
//| - accepts only orders signed with HMAC-SHA256 (shared secret)    |
//| - sizes the lot from risk % and stop distance                    |
//| - OnTick guardian: closes everything and locks the day when the  |
//|   floating equity is down InpDailyKillPct from the day's start   |
//| - partial close at +InpPartial R and stop to break-even          |
//| - spread cap and rollover block (21:45-23:15 UTC)                |
//| Written without access to a MetaTrader compiler: compile and run |
//| it on a DEMO account first.                                      |
//+------------------------------------------------------------------+
#property strict
#property version "5.00"
#include <Trade/Trade.mqh>

input string InpHost          = "127.0.0.1";
input int    InpPort          = 18777;
input string InpSecret        = "change-me";      // same secret as the Python bridge
input double InpDailyKillPct  = 3.2;              // close all and lock the day at this loss
input double InpMaxSpreadPts  = 35;               // no entry above this spread (points)
input double InpPartialFrac   = 0.5;              // share closed at the partial level
input long   InpMagic         = 550055;
input int    InpTickReportMs  = 1000;

CTrade   trade;
int      sock = INVALID_HANDLE;
string   rxBuffer = "";
double   dayStartEquity = 0.0;
int      dayOfYear = -1;
bool     dayLocked = false;
ulong    lastReport = 0;

struct Managed { ulong ticket; string id; double entry; double riskDist; double partialR; bool partialDone; double mae; };
Managed  managed[];

//--- helpers ---------------------------------------------------------
string JsonStr(const string s, const string key)
  {
   int p = StringFind(s, "\"" + key + "\":\"");
   if(p < 0) return "";
   p += StringLen(key) + 4;
   int e = StringFind(s, "\"", p);
   return (e < 0) ? "" : StringSubstr(s, p, e - p);
  }

double JsonNum(const string s, const string key)
  {
   int p = StringFind(s, "\"" + key + "\":");
   if(p < 0) return 0.0;
   p += StringLen(key) + 3;
   int e = p;
   while(e < StringLen(s))
     {
      ushort c = StringGetCharacter(s, e);
      if(c == ',' || c == '}') break;
      e++;
     }
   return StringToDouble(StringSubstr(s, p, e - p));
  }

string Hex(const uchar &a[])
  {
   string out = "";
   for(int i = 0; i < ArraySize(a); i++) out += StringFormat("%02x", a[i]);
   return out;
  }

string HmacSha256(const string message, const string secret)
  {
   uchar key[], msg[], empty[], ipad[], opad[], inner[], outer[], h1[], h2[];
   StringToCharArray(secret, key, 0, StringLen(secret), CP_UTF8);
   StringToCharArray(message, msg, 0, StringLen(message), CP_UTF8);
   if(ArraySize(key) > 64) { uchar kh[]; CryptEncode(CRYPT_HASH_SHA256, key, empty, kh); ArrayCopy(key, kh); ArrayResize(key, 32); }
   ArrayResize(ipad, 64); ArrayResize(opad, 64);
   for(int i = 0; i < 64; i++)
     {
      uchar k = (i < ArraySize(key)) ? key[i] : 0;
      ipad[i] = (uchar)(k ^ 0x36);
      opad[i] = (uchar)(k ^ 0x5c);
     }
   ArrayCopy(inner, ipad); ArrayCopy(inner, msg, 64);
   CryptEncode(CRYPT_HASH_SHA256, inner, empty, h1);
   ArrayCopy(outer, opad); ArrayCopy(outer, h1, 64);
   CryptEncode(CRYPT_HASH_SHA256, outer, empty, h2);
   return Hex(h2);
  }

bool InRollover()
  {
   MqlDateTime g; TimeToStruct(TimeGMT(), g);
   double h = g.hour + g.min / 60.0;
   return (h >= 21.75 && h < 23.25);
  }

void Send(const string line)
  {
   if(sock == INVALID_HANDLE) return;
   uchar data[];
   string s = line + "\n";
   int n = StringToCharArray(s, data, 0, StringLen(s), CP_UTF8);
   if(SocketSend(sock, data, n) < 0) { SocketClose(sock); sock = INVALID_HANDLE; }
  }

bool Connect()
  {
   if(sock != INVALID_HANDLE) return true;
   sock = SocketCreate();
   if(sock == INVALID_HANDLE) return false;
   if(!SocketConnect(sock, InpHost, InpPort, 1000)) { SocketClose(sock); sock = INVALID_HANDLE; return false; }
   Send("{\"type\":\"hello\"}");
   return true;
  }

//--- guardian --------------------------------------------------------
void CloseAll(const string reason)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == InpMagic) trade.PositionClose(t);
     }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(OrderSelect(t) && OrderGetInteger(ORDER_MAGIC) == InpMagic) trade.OrderDelete(t);
     }
   Send("{\"type\":\"guard\",\"reason\":\"" + reason + "\"}");
  }

void Guardian()
  {
   MqlDateTime now; TimeToStruct(TimeCurrent(), now);     // broker day = prop-firm day
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(now.day_of_year != dayOfYear)
     {
      dayOfYear = now.day_of_year;
      dayStartEquity = MathMax(eq, AccountInfoDouble(ACCOUNT_BALANCE));
      dayLocked = false;
      GlobalVariableSet("PGV5_dayStart", dayStartEquity);
      GlobalVariableSet("PGV5_dayOfYear", dayOfYear);
      GlobalVariableSet("PGV5_locked", 0);
     }
   if(!dayLocked && eq <= dayStartEquity * (1.0 - InpDailyKillPct / 100.0))
     {
      dayLocked = true;
      GlobalVariableSet("PGV5_locked", 1);
      CloseAll("daily_kill");
     }
  }

//--- partial + break-even -------------------------------------------
void ManagePositions()
  {
   for(int i = ArraySize(managed) - 1; i >= 0; i--)
     {
      if(!PositionSelectByTicket(managed[i].ticket)) continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      long type = PositionGetInteger(POSITION_TYPE);
      double px = (type == POSITION_TYPE_BUY) ? SymbolInfoDouble(sym, SYMBOL_BID) : SymbolInfoDouble(sym, SYMBOL_ASK);
      double dir = (type == POSITION_TYPE_BUY) ? 1.0 : -1.0;
      double r = dir * (px - managed[i].entry) / managed[i].riskDist;
      if(r < managed[i].mae) managed[i].mae = r;
      if(!managed[i].partialDone && managed[i].partialR > 0 && r >= managed[i].partialR)
        {
         double vol = PositionGetDouble(POSITION_VOLUME);
         double step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
         double part = MathFloor(vol * InpPartialFrac / step) * step;
         if(part >= SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN) && vol - part >= SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN))
            trade.PositionClosePartial(managed[i].ticket, part);
         double spread = SymbolInfoInteger(sym, SYMBOL_SPREAD) * SymbolInfoDouble(sym, SYMBOL_POINT);
         double be = NormalizeDouble(managed[i].entry + dir * spread, (int)SymbolInfoInteger(sym, SYMBOL_DIGITS));
         trade.PositionModify(managed[i].ticket, be, PositionGetDouble(POSITION_TP));
         managed[i].partialDone = true;
        }
     }
  }

//--- orders ----------------------------------------------------------
void ExecuteOrder(const string line)
  {
   int sp = StringFind(line, ",\"sig\":\"");
   if(sp < 0) return;
   string body = StringSubstr(line, 0, sp) + "}";
   string sig = JsonStr(line, "sig");
   if(HmacSha256(body, InpSecret) != sig) { Print("PropGuard: bad signature, order ignored"); return; }
   if(dayLocked || InRollover()) return;

   string sym = JsonStr(line, "symbol"), id = JsonStr(line, "id");
   int side = (int)JsonNum(line, "side");
   double riskPct = JsonNum(line, "risk_pct"), sl = JsonNum(line, "sl"), tp = JsonNum(line, "tp");
   if(!SymbolSelect(sym, true)) return;
   if(SymbolInfoInteger(sym, SYMBOL_SPREAD) > InpMaxSpreadPts) return;

   double price = (side > 0) ? SymbolInfoDouble(sym, SYMBOL_ASK) : SymbolInfoDouble(sym, SYMBOL_BID);
   double dist = MathAbs(price - sl);
   double tickVal = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE), tickSize = SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE);
   if(dist <= 0 || tickVal <= 0 || tickSize <= 0) return;
   double riskMoney = AccountInfoDouble(ACCOUNT_BALANCE) * riskPct / 100.0;
   // never risk more than what is left before the daily kill
   double room = AccountInfoDouble(ACCOUNT_EQUITY) - dayStartEquity * (1.0 - InpDailyKillPct / 100.0);
   riskMoney = MathMin(riskMoney, MathMax(room, 0.0));
   double step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   double lots = MathFloor(riskMoney / (dist / tickSize * tickVal) / step) * step;
   lots = MathMin(lots, SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX));
   if(lots < SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN)) return;

   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   trade.SetExpertMagicNumber(InpMagic);
   bool ok = (side > 0) ? trade.Buy(lots, sym, 0.0, NormalizeDouble(sl, digits), NormalizeDouble(tp, digits), id)
                        : trade.Sell(lots, sym, 0.0, NormalizeDouble(sl, digits), NormalizeDouble(tp, digits), id);
   if(!ok) return;
   ulong deal = trade.ResultDeal();
   if(!HistoryDealSelect(deal)) return;
   int n = ArraySize(managed);
   ArrayResize(managed, n + 1);
   managed[n].ticket = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
   managed[n].id = id;
   managed[n].entry = HistoryDealGetDouble(deal, DEAL_PRICE);
   managed[n].riskDist = dist;
   managed[n].partialR = JsonNum(line, "partial_r");
   managed[n].partialDone = false;
   managed[n].mae = 0.0;
  }

void ReadSocket()
  {
   if(!Connect()) return;
   uint len = SocketIsReadable(sock);
   if(len > 0)
     {
      uchar data[];
      int got = SocketRead(sock, data, len, 50);
      if(got > 0) rxBuffer += CharArrayToString(data, 0, got, CP_UTF8);
     }
   int nl;
   while((nl = StringFind(rxBuffer, "\n")) >= 0)
     {
      string line = StringSubstr(rxBuffer, 0, nl);
      rxBuffer = StringSubstr(rxBuffer, nl + 1);
      if(JsonStr(line, "type") == "order") ExecuteOrder(line);
     }
  }

void ReadFallbackFiles()
  {
   string name;
   long h = FileFindFirst("propguard_order_*.json", name, FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   do
     {
      int f = FileOpen(name, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
      if(f != INVALID_HANDLE)
        {
         string line = FileReadString(f);
         FileClose(f);
         FileDelete(name, FILE_COMMON);
         if(JsonStr(line, "type") == "order") ExecuteOrder(line);
        }
     }
   while(FileFindNext(h, name));
   FileFindClose(h);
  }

void Report()
  {
   if(GetTickCount64() - lastReport < (ulong)InpTickReportMs) return;
   lastReport = GetTickCount64();
   string spreads = "";
   for(int i = 0; i < SymbolsTotal(true); i++)
     {
      string s = SymbolName(i, true);
      spreads += (i > 0 ? "," : "") + "\"" + s + "\":" + IntegerToString(SymbolInfoInteger(s, SYMBOL_SPREAD));
     }
   Send(StringFormat("{\"type\":\"tick\",\"equity\":%.2f,\"balance\":%.2f,\"spread_pts\":{%s}}",
                     AccountInfoDouble(ACCOUNT_EQUITY), AccountInfoDouble(ACCOUNT_BALANCE), spreads));
  }

//--- events ----------------------------------------------------------
int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagic);
   if(GlobalVariableCheck("PGV5_dayOfYear"))   // survive a terminal restart inside the same day
     {
      dayOfYear = (int)GlobalVariableGet("PGV5_dayOfYear");
      dayStartEquity = GlobalVariableGet("PGV5_dayStart");
      dayLocked = GlobalVariableGet("PGV5_locked") > 0;
     }
   EventSetMillisecondTimer(200);
   Connect();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { EventKillTimer(); if(sock != INVALID_HANDLE) SocketClose(sock); }

void OnTick() { Guardian(); ManagePositions(); }

void OnTimer() { Guardian(); ManagePositions(); ReadSocket(); ReadFallbackFiles(); Report(); }

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;
   ulong pos = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   if(PositionSelectByTicket(pos)) return;                 // partial close: position still open
   for(int i = 0; i < ArraySize(managed); i++)
     {
      if(managed[i].ticket != pos) continue;
      double profit = 0.0, volIn = 0.0, riskMoney = 0.0;
      if(HistorySelectByPosition(pos))
         for(int d = 0; d < HistoryDealsTotal(); d++)
           {
            ulong dt = HistoryDealGetTicket(d);
            profit += HistoryDealGetDouble(dt, DEAL_PROFIT) + HistoryDealGetDouble(dt, DEAL_SWAP) + HistoryDealGetDouble(dt, DEAL_COMMISSION);
            if(HistoryDealGetInteger(dt, DEAL_ENTRY) == DEAL_ENTRY_IN) volIn += HistoryDealGetDouble(dt, DEAL_VOLUME);
           }
      string sym = HistoryDealGetString(trans.deal, DEAL_SYMBOL);
      riskMoney = managed[i].riskDist / SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE) * SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE) * volIn;
      double r = (riskMoney > 0) ? profit / riskMoney : 0.0;
      Send(StringFormat("{\"type\":\"closed\",\"id\":\"%s\",\"result_r\":%.4f,\"mae_r\":%.4f}", managed[i].id, r, managed[i].mae));
      ArrayRemove(managed, i, 1);
      break;
     }
  }
//+------------------------------------------------------------------+
