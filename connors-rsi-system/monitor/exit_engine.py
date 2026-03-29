from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional, Set

from watchlist.models import PositionRow, PositionStatus


class ExitAction(str, Enum):
    NONE = "NONE"
    STOP_LOSS = "STOP_LOSS"
    TRAIL_PEAK = "TRAIL_PEAK"
    TARGET_HIT = "TARGET_HIT"
    RSI_EXIT = "RSI_EXIT"
    PARTIAL_VOLATILITY = "PARTIAL_VOLATILITY"
    TIMEOUT = "TIMEOUT"
    RALLY_ALERT = "RALLY_ALERT"


@dataclass
class ExitDecision:
    action: ExitAction
    reason: str
    detail: str = ""
    alert_only: bool = False


@dataclass
class ExitContext:
    connors_rsi: Optional[float] = None
    daily_close: Optional[float] = None
    ma200: Optional[float] = None
    atr_current: Optional[float] = None
    atr_baseline: Optional[float] = None
    rsi_for_vol: Optional[float] = None
    current_date: Optional[date] = None
    intraday_high: Optional[float] = None
    partial_vol_done: bool = False
    rally_notified: Set[float] = field(default_factory=set)


@dataclass
class ExitEngineConfig:
    stop_loss_pct: float = 0.08
    crsi_exit_threshold: float = 70.0
    max_hold_days: int = 5
    rally_alert_pcts: tuple[float, ...] = (0.02, 0.03, 0.04)
    volatility_atr_multiple: float = 2.0
    partial_exit_ratio: float = 0.5
    trail_from_peak_pct: float = 0.0
    enable_volatility_partial: bool = False


class ExitEngine:
    def __init__(self, cfg: ExitEngineConfig) -> None:
        self.cfg = cfg

    def evaluate(
        self,
        pos: PositionRow,
        price: float,
        ctx: ExitContext,
    ) -> List[ExitDecision]:
        if pos.status != PositionStatus.HOLDING.value:
            return []

        entry = pos.entry_price
        shares = pos.shares or 0
        if not entry or shares <= 0:
            return []

        # 1位: 損切り
        if pos.stop_price is not None and price <= pos.stop_price:
            return [
                ExitDecision(
                    ExitAction.STOP_LOSS,
                    "STOP_LOSS",
                    f"価格 {price} <= ストップ {pos.stop_price}",
                )
            ]

        if ctx.daily_close is not None:
            if ctx.daily_close < entry * (1.0 - self.cfg.stop_loss_pct):
                return [
                    ExitDecision(
                        ExitAction.STOP_LOSS,
                        "STOP_CLOSE_PCT",
                        f"終値 {ctx.daily_close} < エントリー×{1 - self.cfg.stop_loss_pct:.2f}",
                    )
                ]
            if ctx.ma200 is not None and ctx.daily_close < ctx.ma200:
                return [
                    ExitDecision(
                        ExitAction.STOP_LOSS,
                        "STOP_MA200",
                        "終値が200日線下抜け",
                    )
                ]

        # 2位: 高値からのトレール（全株まとめて売却・100株単位向け）
        if self.cfg.trail_from_peak_pct > 0 and pos.peak_price is not None:
            peak = float(pos.peak_price)
            if peak > 0 and price <= peak * (1.0 - self.cfg.trail_from_peak_pct):
                return [
                    ExitDecision(
                        ExitAction.TRAIL_PEAK,
                        "TRAIL_FROM_PEAK",
                        f"現在 {price} ≤ 高値 {peak} × (1−{self.cfg.trail_from_peak_pct:.4f})",
                    )
                ]

        # 3位: RSI 過買い出口
        if (
            ctx.connors_rsi is not None
            and ctx.connors_rsi > self.cfg.crsi_exit_threshold
        ):
            return [
                ExitDecision(
                    ExitAction.RSI_EXIT,
                    "CRSI_GT_70",
                    f"ConnorsRSI={ctx.connors_rsi:.2f}",
                )
            ]

        rally_decisions: List[ExitDecision] = []
        for pct in self.cfg.rally_alert_pcts:
            if pct in ctx.rally_notified:
                continue
            if price >= entry * (1.0 + pct):
                rally_decisions.append(
                    ExitDecision(
                        ExitAction.RALLY_ALERT,
                        f"RALLY_{int(pct * 100)}PCT",
                        f"+{pct * 100:.0f}% 到達（手動判断）",
                        alert_only=True,
                    )
                )

        # 4位: 日中高値ターゲット
        hi = ctx.intraday_high if ctx.intraday_high is not None else price
        if pos.target_price is not None and (
            hi >= pos.target_price or price >= pos.target_price
        ):
            return rally_decisions + [
                ExitDecision(
                    ExitAction.TARGET_HIT,
                    "TARGET_HIT",
                    f"目標到達 価格={price} 高値={hi} 目標={pos.target_price}",
                )
            ]

        # 5位: ボラティリティ部分利確（オプション・100株では通常オフ）
        if (
            self.cfg.enable_volatility_partial
            and not ctx.partial_vol_done
            and ctx.atr_current is not None
            and ctx.atr_baseline is not None
            and ctx.atr_baseline > 0
            and ctx.atr_current
            >= ctx.atr_baseline * self.cfg.volatility_atr_multiple
            and ctx.rsi_for_vol is not None
            and ctx.rsi_for_vol > 50
        ):
            return rally_decisions + [
                ExitDecision(
                    ExitAction.PARTIAL_VOLATILITY,
                    "HIGH_VOL_PARTIAL",
                    "ATR急拡大かつRSI>50",
                )
            ]

        # 6位: タイムアウト
        if pos.entry_date and ctx.current_date:
            days = (ctx.current_date - pos.entry_date).days
            if days >= self.cfg.max_hold_days:
                return rally_decisions + [
                    ExitDecision(
                        ExitAction.TIMEOUT,
                        "MAX_HOLD_DAYS",
                        f"{days}営業日相当経過",
                    )
                ]

        return rally_decisions
