from __future__ import annotations

import asyncio
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import yaml

from alerts.notifier import AlertNotifier
from services.excel_market import build_excel_price_fetcher
from services.ops import project_root as app_project_root
from monitor.exit_engine import ExitAction, ExitContext, ExitEngine, ExitEngineConfig
from monitor.order_manager import OrderManager
from monitor.price_feed import PriceTick
from watchlist.db import WatchlistDB
from watchlist.models import PositionStatus

logger = logging.getLogger(__name__)


def _resolve_db_path(cfg: dict[str, Any], root: Path) -> Path:
    raw = cfg.get("database", {}).get("path", "data/watchlist.db")
    p = Path(raw)
    return p if p.is_absolute() else (root / p)


def _engine_cfg(cfg: dict[str, Any]) -> ExitEngineConfig:
    s = cfg.get("strategy", {})
    e = cfg.get("exit", {})
    trail = float(e.get("trail_from_peak_pct", 0) or 0)
    return ExitEngineConfig(
        stop_loss_pct=abs(float(e.get("stop_loss_pct", -0.08))),
        crsi_exit_threshold=float(s.get("crsi_exit_threshold", 70)),
        max_hold_days=int(s.get("max_hold_days", 5)),
        rally_alert_pcts=tuple(e.get("rally_alert_pcts", [0.02, 0.03, 0.04])),
        volatility_atr_multiple=float(e.get("volatility_atr_multiple", 2.0)),
        partial_exit_ratio=float(e.get("partial_exit_ratio", 0.5)),
        trail_from_peak_pct=trail,
        enable_volatility_partial=bool(e.get("enable_volatility_partial", False)),
    )


def default_price_fetcher(
    prices: Dict[str, float],
) -> Callable[[str], Optional[PriceTick]]:
    def fetch(symbol: str) -> Optional[PriceTick]:
        p = prices.get(symbol.upper())
        if p is None:
            return None
        return PriceTick(symbol=symbol.upper(), price=p)

    return fetch


def _rally_pct_from_reason(reason: str) -> Optional[float]:
    m = re.match(r"RALLY_(\d+)PCT", reason)
    if not m:
        return None
    return int(m.group(1)) / 100.0


async def monitor_loop(
    config_path: Path,
    price_fetcher: Optional[Callable[[str], Optional[PriceTick]]] = None,
) -> None:
    root = config_path.parent
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    db = WatchlistDB(_resolve_db_path(cfg, root))
    ecfg = _engine_cfg(cfg)
    engine = ExitEngine(ecfg)
    orders = OrderManager(db)
    alerts_cfg = cfg.get("alerts", {})
    notifier = AlertNotifier(
        line_token=alerts_cfg.get("line_token", "") or "",
        slack_webhook=alerts_cfg.get("slack_webhook", "") or "",
    )
    interval = float(cfg.get("monitor", {}).get("price_check_interval_sec", 5))
    today = date.today()
    rally_state: Dict[str, set[float]] = {}

    if price_fetcher is None:
        md = cfg.get("market_data") or {}
        if (md.get("source") or "").strip().lower() == "excel":
            price_fetcher = build_excel_price_fetcher(
                config_path,
                project_root=app_project_root(),
            )
            logger.info(
                "株価ソース: MarketSpeed 連携 Excel (%s)",
                (md.get("excel_path") or "").strip() or "(パス未設定)",
            )
        else:
            prices = {}
            for row in db.list_open_for_monitor():
                if row.status == PositionStatus.HOLDING.value and row.entry_price:
                    prices[row.symbol] = float(row.entry_price)
            price_fetcher = default_price_fetcher(prices)
            logger.info("株価ソース: スタブ（エントリー価格固定）※ yfinance では監視しません")

    logger.info("監視ループ開始 interval=%ss", interval)

    while True:
        holding = [
            p
            for p in db.list_open_for_monitor()
            if p.status == PositionStatus.HOLDING.value
        ]
        for pos in holding:
            tick = price_fetcher(pos.symbol)
            if tick is None:
                continue
            entry = pos.entry_price
            if entry is None:
                continue
            prev_peak = pos.peak_price if pos.peak_price is not None else float(entry)
            new_peak = max(float(prev_peak), float(tick.price))
            if pos.id is not None and (
                pos.peak_price is None or new_peak > float(pos.peak_price or 0)
            ):
                db.update_position(pos.id, peak_price=new_peak)
            pos.peak_price = new_peak
            notified = rally_state.setdefault(pos.symbol, set())
            ctx = ExitContext(
                current_date=today,
                intraday_high=tick.high or tick.price,
                rally_notified=notified,
            )
            decisions = engine.evaluate(pos, tick.price, ctx)
            for d in decisions:
                if d.action == ExitAction.RALLY_ALERT and d.alert_only:
                    rp = _rally_pct_from_reason(d.reason)
                    if rp is not None:
                        notified.add(rp)
                    await notifier.alert(
                        "騰落アラート", f"{pos.symbol} {d.detail}", important=False
                    )
                    continue
                if d.action == ExitAction.STOP_LOSS:
                    await notifier.alert(
                        "損切り", f"{pos.symbol} {d.detail}", important=True
                    )
                    await orders.market_sell(pos, d.reason, tick.price, today)
                elif d.action == ExitAction.TRAIL_PEAK:
                    await notifier.alert(
                        "高値トレール", f"{pos.symbol} {d.detail}", important=True
                    )
                    await orders.market_sell(pos, d.reason, tick.price, today)
                elif d.action == ExitAction.TARGET_HIT:
                    await notifier.alert(
                        "目標到達", f"{pos.symbol} {d.detail}", important=True
                    )
                    await orders.limit_sell(pos, tick.price, d.reason, today)
                elif d.action == ExitAction.RSI_EXIT:
                    await notifier.alert(
                        "RSI出口", f"{pos.symbol} {d.detail}", important=True
                    )
                    await orders.market_sell(pos, d.reason, tick.price, today)
                elif d.action == ExitAction.PARTIAL_VOLATILITY:
                    await notifier.alert(
                        "部分利確", f"{pos.symbol} {d.detail}", important=False
                    )
                    await orders.partial_sell(
                        pos, ecfg.partial_exit_ratio, d.reason, tick.price
                    )
                elif d.action == ExitAction.TIMEOUT:
                    await notifier.alert(
                        "タイムアウト", f"{pos.symbol} {d.detail}", important=True
                    )
                    await orders.market_sell(pos, d.reason, tick.price, today)

        await asyncio.sleep(interval)
