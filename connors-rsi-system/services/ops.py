from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from analysis.indicators import target_price_from_atr
from watchlist.db import WatchlistDB
from watchlist.models import PositionStatus
from watchlist.position_manager import PositionManager


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_config_path() -> Path:
    env = os.environ.get("CONNORS_CONFIG")
    if env:
        return Path(env)
    return project_root() / "config.yaml"


def load_full_config(config_path: Path | None = None) -> dict[str, Any]:
    p = config_path or load_config_path()
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_watchlist_db(config_path: Path | None = None) -> WatchlistDB:
    root = project_root()
    cfg = load_full_config(config_path)
    raw = cfg.get("database", {}).get("path", "data/watchlist.db")
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return WatchlistDB(path)


def add_screen_symbols(symbols: list[str], config_path: Path | None = None) -> dict[str, Any]:
    db = get_watchlist_db(config_path)
    pm = PositionManager(db)
    today = date.today()
    syms = [s.strip().upper() for s in symbols if s.strip()]
    for s in syms:
        pm.register_screened(s, today)
    return {"added": syms, "count": len(syms)}


def seed_demo_holding(config_path: Path | None = None) -> dict[str, Any]:
    cfg = load_full_config(config_path)
    db = get_watchlist_db(config_path)
    pm = PositionManager(db)
    today = date.today()
    rows = db.list_by_status(PositionStatus.HOLDING.value)
    if rows:
        return {
            "created": False,
            "message": "既に保有ポジションがあります（デモ作成をスキップ）",
            "holdings": [{"symbol": r.symbol, "id": r.id} for r in rows],
        }
    e = cfg.get("exit", {})
    entry = 100.0
    atr_v = 2.0
    tgt = target_price_from_atr(
        entry,
        atr_v,
        multiplier=float(e.get("atr_multiplier", 2.0)),
        min_pct=float(e.get("min_target_pct", 0.02)),
        max_pct=float(e.get("max_target_pct", 0.08)),
    )
    stop = entry * (1.0 - abs(float(e.get("stop_loss_pct", -0.08))))
    rid = pm.register_screened("DEMO", today, crsi_at_entry=5.0)
    pm.open_holding(
        rid,
        entry_price=entry,
        entry_d=today,
        shares=10,
        target_price=tgt,
        stop_price=stop,
        crsi_at_entry=5.0,
    )
    return {
        "created": True,
        "symbol": "DEMO",
        "entry": entry,
        "target": tgt,
        "stop": stop,
        "row_id": rid,
    }


def promote_to_holding(
    symbol: str,
    entry_price: float,
    shares: int,
    *,
    atr_estimate: float | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    sym = symbol.strip().upper()
    db = get_watchlist_db(config_path)
    watching = [
        r
        for r in db.list_by_status(PositionStatus.WATCHING.value)
        if r.symbol == sym
    ]
    if not watching:
        return {"ok": False, "message": f"{sym} の WATCHING 行がありません。先にウォッチ登録してください。"}
    row = watching[-1]
    cfg = load_full_config(config_path)
    e = cfg.get("exit", {})
    atr = atr_estimate if atr_estimate is not None else entry_price * 0.02
    tgt = target_price_from_atr(
        entry_price,
        atr,
        multiplier=float(e.get("atr_multiplier", 2.0)),
        min_pct=float(e.get("min_target_pct", 0.02)),
        max_pct=float(e.get("max_target_pct", 0.08)),
    )
    stop = entry_price * (1.0 - abs(float(e.get("stop_loss_pct", -0.08))))
    pm = PositionManager(db)
    if row.id is None:
        return {"ok": False, "message": "内部エラー: id がありません"}
    pm.open_holding(
        row.id,
        entry_price=entry_price,
        entry_d=date.today(),
        shares=int(shares),
        target_price=tgt,
        stop_price=stop,
        crsi_at_entry=row.crsi_at_entry,
    )
    return {
        "ok": True,
        "symbol": sym,
        "entry_price": entry_price,
        "shares": shares,
        "target_price": tgt,
        "stop_price": stop,
        "row_id": row.id,
    }


def portfolio_summary(config_path: Path | None = None) -> dict[str, Any]:
    db = get_watchlist_db(config_path)
    all_rows = db.all_rows()
    w = sum(1 for r in all_rows if r.status == PositionStatus.WATCHING.value)
    h = sum(1 for r in all_rows if r.status == PositionStatus.HOLDING.value)
    c = sum(1 for r in all_rows if r.status == PositionStatus.CLOSED.value)
    exposure = 0.0
    for r in all_rows:
        if r.status == PositionStatus.HOLDING.value and r.entry_price and r.shares:
            exposure += r.entry_price * r.shares
    return {
        "watching": w,
        "holding": h,
        "closed": c,
        "exposure_usd": round(exposure, 2),
    }
