from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from analysis.indicators import compute_connors_rsi_series, sma


@dataclass
class SignalFilterConfig:
    crsi_buy_threshold: float = 10.0
    ma_period: int = 200
    volume_lookback: int = 20
    volume_multiplier: float = 1.5
    min_price_usd: float = 5.0
    min_market_cap_usd: float = 500_000_000


def entry_signal_mask(
    ohlcv: pd.DataFrame,
    cfg: Optional[SignalFilterConfig] = None,
    market_cap: Optional[pd.Series] = None,
) -> pd.Series:
    """
    ohlcv: columns open, high, low, close, volume (index = date)
    market_cap: optional series aligned with ohlcv index (USD)
    """
    cfg = cfg or SignalFilterConfig()
    close = ohlcv["close"].astype(float)
    vol = ohlcv["volume"].astype(float)
    ma200 = sma(close, cfg.ma_period)
    vol_ma = vol.rolling(cfg.volume_lookback, min_periods=cfg.volume_lookback).mean()
    ind = compute_connors_rsi_series(close)
    crsi = ind["connors_rsi"]

    m = (
        (crsi < cfg.crsi_buy_threshold)
        & (close > ma200)
        & (vol > vol_ma * cfg.volume_multiplier)
        & (close >= cfg.min_price_usd)
    )
    if market_cap is not None:
        m = m & (market_cap >= cfg.min_market_cap_usd)
    return m.fillna(False)


def filter_entry_candidates(
    ohlcv: pd.DataFrame,
    symbol: str,
    cfg: Optional[SignalFilterConfig] = None,
    market_cap: Optional[float] = None,
) -> bool:
    c = cfg or SignalFilterConfig()
    if len(ohlcv) < max(c.ma_period, 100) + 5:
        return False
    mc_series = None
    if market_cap is not None:
        mc_series = pd.Series(market_cap, index=ohlcv.index)
    mask = entry_signal_mask(ohlcv, cfg, mc_series)
    return bool(mask.iloc[-1])
