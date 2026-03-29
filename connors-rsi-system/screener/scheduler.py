from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any, Callable, List, Optional

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def start_monday_screener_job(
    config_path: str | Path,
    job_fn: Callable[[dict[str, Any]], List[str]],
    *,
    timezone: str = "America/New_York",
) -> None:
    """
    月曜 10:00（設定の screener セクションで変更可）に job_fn(cfg) を実行。
    """
    cfg = load_config(config_path)
    sc = cfg.get("screener", {})
    wd = int(sc.get("run_weekday", 0))
    h = int(sc.get("run_hour", 10))
    m = int(sc.get("run_minute", 0))
    tz = sc.get("timezone", timezone)

    sched = BlockingScheduler(timezone=tz)

    def wrapped() -> None:
        c = load_config(config_path)
        try:
            job_fn(c)
        except Exception:
            logger.exception("スクリーナージョブ失敗")

    sched.add_job(
        wrapped,
        CronTrigger(day_of_week=wd, hour=h, minute=m, timezone=tz),
        id="monday_screener",
        replace_existing=True,
    )
    logger.info("スケジューラ開始: weekday=%s %02d:%02d %s", wd, h, m, tz)
    sched.start()


def demo_register_symbols_from_list(
    symbols: List[str],
    db_path: str,
    screened_date: Optional[date] = None,
) -> None:
    """手動デモ: 銘柄リストをウォッチリストに登録。"""
    from watchlist.db import WatchlistDB
    from watchlist.position_manager import PositionManager

    db = WatchlistDB(db_path)
    pm = PositionManager(db)
    d = screened_date or date.today()
    for s in symbols:
        pm.register_screened(s.strip().upper(), d)
    logger.info("登録完了: %s 件", len(symbols))
