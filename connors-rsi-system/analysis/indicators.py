from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.astype(float).diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def compute_streak(close: pd.Series) -> pd.Series:
    c = close.astype(float).values
    n = len(c)
    streak = np.zeros(n, dtype=float)
    for i in range(1, n):
        if c[i] > c[i - 1]:
            streak[i] = streak[i - 1] + 1 if streak[i - 1] > 0 else 1.0
        elif c[i] < c[i - 1]:
            streak[i] = streak[i - 1] - 1 if streak[i - 1] < 0 else -1.0
        else:
            streak[i] = 0.0
    return pd.Series(streak, index=close.index)


def percent_rank_roc(close: pd.Series, window: int = 100) -> pd.Series:
    roc1 = close.pct_change()
    out = pd.Series(index=close.index, dtype=float)
    for i in range(len(close)):
        if i < window - 1:
            out.iloc[i] = np.nan
            continue
        win = roc1.iloc[i - window + 1 : i + 1]
        cur = roc1.iloc[i]
        if pd.isna(cur):
            out.iloc[i] = np.nan
            continue
        valid = win.dropna()
        if valid.empty:
            out.iloc[i] = np.nan
            continue
        pr = (valid <= cur).sum() / len(valid) * 100.0
        out.iloc[i] = pr
    return out


def compute_connors_rsi_series(close: pd.Series) -> pd.DataFrame:
    rsi2 = _rsi(close, 2)
    streak = compute_streak(close)
    streak_rsi = _rsi(pd.Series(streak.values, index=close.index), 2)
    prank = percent_rank_roc(close, 100)
    crsi = (rsi2 + streak_rsi + prank) / 3.0
    return pd.DataFrame(
        {
            "rsi2": rsi2,
            "streak_rsi": streak_rsi,
            "percent_rank": prank,
            "connors_rsi": crsi,
        },
        index=close.index,
    )


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 2) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def dynamic_target_pct(
    entry_price: float,
    atr_value: float,
    *,
    multiplier: float = 2.0,
    min_pct: float = 0.02,
    max_pct: float = 0.08,
) -> float:
    if entry_price <= 0 or atr_value is None or (isinstance(atr_value, float) and np.isnan(atr_value)):
        return min_pct
    atr_pct = atr_value / entry_price
    raw = atr_pct * multiplier
    return float(max(min_pct, min(max_pct, raw)))


def target_price_from_atr(
    entry_price: float,
    atr_value: float,
    **kwargs: float,
) -> float:
    pct = dynamic_target_pct(entry_price, atr_value, **kwargs)
    return entry_price * (1.0 + pct)
