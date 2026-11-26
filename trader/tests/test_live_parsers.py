"""Parsers for Binance REST answers, checked against real payloads captured on 2026-11-26."""
import pandas as pd

from kenui_trader import live

OI = [{"symbol": "1000PEPEUSDT", "sumOpenInterest": "20725905796.0", "sumOpenInterestValue": "73807023.13", "CMCCirculatingSupply": "4.1e11", "timestamp": 1795659300000},
      {"symbol": "1000PEPEUSDT", "sumOpenInterest": "20890741517.0", "sumOpenInterestValue": "74593108.38", "CMCCirculatingSupply": "4.1e11", "timestamp": 1795659600000}]
LS = [{"symbol": "BTCUSDT", "longAccount": "0.6495", "longShortRatio": "1.8529", "shortAccount": "0.3505", "timestamp": 1795659300000},
      {"symbol": "BTCUSDT", "longAccount": "0.6493", "longShortRatio": "1.8516", "shortAccount": "0.3507", "timestamp": 1795659600000}]
FR = [{"symbol": "BTCUSDT", "fundingTime": 1795622400000, "fundingRate": "0.00006085", "markPrice": "58319.8", "rateType": "Regular"},
      {"symbol": "BTCUSDT", "fundingTime": 1795651200003, "fundingRate": "0.00007969", "markPrice": "60429.9", "rateType": "Regular"}]
KL = [[1795659300000, "-0.00051476", "-0.00012810", "-0.00062378", "-0.00042179", "0", 1795659599999, "0", 60, "0", "0", "0"],
      [1795659600000, "-0.00042714", "0.00035832", "-0.00063758", "-0.00063758", "0", 1795659899999, "0", 53, "0", "0", "0"]]


def fake_get(hosts, path, params=None, tries=3):
    if "openInterestHist" in path:
        return OI
    if "/futures/data/" in path:
        return LS
    if "fundingRate" in path:
        return FR
    return KL


def test_parsers(monkeypatch):
    monkeypatch.setattr(live, "get", fake_get)
    m = live.metrics("BTCUSDT")
    assert list(m.columns) == ["sum_open_interest", "sum_open_interest_value", "count_toptrader_long_short_ratio",
                               "sum_toptrader_long_short_ratio", "count_long_short_ratio"]
    assert isinstance(m.index, pd.DatetimeIndex) and len(m) == 2 and m["sum_open_interest"].iloc[-1] == 20890741517.0
    f = live.funding("BTCUSDT")
    assert f.index[-1].second == 0 and abs(f["last_funding_rate"].iloc[-1] - 0.00007969) < 1e-12
    k = live.fut_klines("BTCUSDT", kind="premiumIndexKlines")
    assert isinstance(k.index, pd.DatetimeIndex) and abs(k["close"].iloc[0] + 0.00042179) < 1e-12


def test_store_merge_with_rest_frames(monkeypatch):
    """Archive-shaped history + REST-shaped top-up must merge into a valid panel."""
    from research import panel as P
    monkeypatch.setattr(live, "get", fake_get)
    idx = pd.date_range("2026-11-26 00:00", periods=30, freq="5min", tz="UTC")
    k = pd.DataFrame(1.0, index=idx, columns=live.KEEP)
    arch_m = pd.DataFrame({"sum_open_interest": 1.0, "sum_open_interest_value": 2.0, "count_toptrader_long_short_ratio": 1.0,
                           "sum_toptrader_long_short_ratio": 1.0, "count_long_short_ratio": 1.0,
                           "sum_taker_long_short_vol_ratio": 1.0}, index=idx)
    m = pd.concat([arch_m, live.metrics("BTCUSDT")])
    m = m[~m.index.duplicated(keep="last")].sort_index()
    df = P.merge({"fut": "BTCUSDT", "spot": "BTCUSDT", "mult": 1}, k, k, k, live.funding("BTCUSDT"), m)
    assert df is not None and {"oi", "top_pos_ls", "acct_ls", "funding_last", "prem"} <= set(df.columns)
