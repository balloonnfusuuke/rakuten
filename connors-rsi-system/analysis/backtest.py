from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from analysis.indicators import compute_connors_rsi_series
from screener.signal_filter import SignalFilterConfig, entry_signal_mask


def run_simple_backtest(
    ohlcv: pd.DataFrame,
    cfg: Optional[SignalFilterConfig] = None,
) -> dict[str, Any]:
    """
    単純シグナル集計（エントリー条件が真になったバー数）。
    完全な約定シミュレーションは未実装。
    """
    cfg = cfg or SignalFilterConfig()
    mask = entry_signal_mask(ohlcv, cfg)
    ind = compute_connors_rsi_series(ohlcv["close"])
    return {
        "bars": len(ohlcv),
        "entry_signals": int(mask.sum()),
        "last_crsi": float(ind["connors_rsi"].iloc[-1])
        if len(ind)
        else None,
    }
