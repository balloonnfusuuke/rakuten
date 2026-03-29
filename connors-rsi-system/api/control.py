from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.market_quotes import fetch_market_quotes, market_source_info
from services.ops import (
    add_screen_symbols,
    load_config_path,
    portfolio_summary,
    project_root,
    promote_to_holding,
    seed_demo_holding,
)

router = APIRouter(prefix="/api", tags=["control"])

_log_lines: deque[str] = deque(maxlen=400)
_monitor_lock = threading.Lock()
_monitor_proc: subprocess.Popen | None = None
_reader_thread: threading.Thread | None = None


def _append_log(line: str) -> None:
    _log_lines.append(line)


def _start_log_reader(proc: subprocess.Popen) -> None:
    def run() -> None:
        if proc.stdout is None:
            return
        for raw in iter(proc.stdout.readline, ""):
            if raw == "" and proc.poll() is not None:
                break
            _append_log(raw.rstrip())

    t = threading.Thread(target=run, daemon=True)
    t.start()
    global _reader_thread
    _reader_thread = t


class ScreenBody(BaseModel):
    symbols: str = Field(..., description="カンマ区切り 例: AAPL,MSFT")


class PromoteBody(BaseModel):
    symbol: str
    entry_price: float = Field(gt=0)
    shares: int = Field(gt=0)
    atr_estimate: float | None = Field(
        default=None,
        description="未指定時は entry の2%を ATR 近似に使用",
    )


@router.get("/summary")
def api_summary() -> dict[str, Any]:
    return portfolio_summary()


@router.get("/logs")
def api_logs(limit: int = 200) -> dict[str, Any]:
    n = max(1, min(limit, 400))
    lines = list(_log_lines)[-n:]
    return {"lines": lines, "count": len(lines)}


def _parse_symbols_param(symbols: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for chunk in symbols.replace(" ", "").split(","):
        if not chunk:
            continue
        u = chunk.upper()
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


@router.get("/quotes")
def api_quotes(symbols: str = "") -> dict[str, Any]:
    """symbols: カンマ区切り。market_data.source=excel のとき MarketSpeed 連携 Excel。"""
    return fetch_market_quotes(_parse_symbols_param(symbols))


@router.get("/market/source")
def api_market_source() -> dict[str, Any]:
    """株価ソース（excel / yfinance）と Excel パスの状態。"""
    return market_source_info()


@router.post("/screen")
def api_screen(body: ScreenBody) -> dict[str, Any]:
    parts = [p.strip() for p in body.symbols.replace(" ", "").split(",") if p.strip()]
    if not parts:
        return {"ok": False, "message": "銘柄が空です"}
    result = add_screen_symbols(parts)
    _append_log(f"[API] ウォッチ登録: {', '.join(result['added'])}")
    return {"ok": True, **result}


@router.post("/demo/seed")
def api_demo_seed() -> dict[str, Any]:
    out = seed_demo_holding()
    if out.get("created"):
        _append_log(
            f"[API] デモ保有作成 {out.get('symbol')} entry={out.get('entry')} target={out.get('target')}"
        )
    else:
        _append_log(f"[API] デモシード: {out.get('message', '')}")
    return {"ok": True, **out}


@router.post("/position/promote")
def api_promote(body: PromoteBody) -> dict[str, Any]:
    out = promote_to_holding(
        body.symbol,
        body.entry_price,
        body.shares,
        atr_estimate=body.atr_estimate,
    )
    if out.get("ok"):
        _append_log(
            f"[API] 保有化 {body.symbol.upper()} @ {body.entry_price} x {body.shares}"
        )
    return out


@router.get("/monitor/status")
def monitor_status() -> dict[str, Any]:
    with _monitor_lock:
        proc = _monitor_proc
        if proc is None:
            return {"running": False, "pid": None, "demo": None}
        code = proc.poll()
        if code is not None:
            return {"running": False, "pid": proc.pid, "exit_code": code, "demo": None}
        return {"running": True, "pid": proc.pid, "demo": getattr(proc, "_demo_flag", None)}


@router.post("/monitor/start")
def monitor_start(demo: bool = False) -> dict[str, Any]:
    global _monitor_proc
    root = project_root()
    main_py = root / "main.py"
    if not main_py.is_file():
        return {"ok": False, "message": f"main.py が見つかりません: {main_py}"}

    cfg = load_config_path()
    with _monitor_lock:
        if _monitor_proc is not None and _monitor_proc.poll() is None:
            return {
                "ok": False,
                "message": "監視プロセスは既に起動中です。先に停止してください。",
                "pid": _monitor_proc.pid,
            }
        args = [sys.executable, str(main_py), "monitor"]
        if demo:
            args.append("--demo")
        env = os.environ.copy()
        env["CONNORS_CONFIG"] = str(cfg.resolve())
        env.setdefault("PYTHONUTF8", "1")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        try:
            proc = subprocess.Popen(
                args,
                cwd=str(root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creationflags,
            )
        except OSError as e:
            return {"ok": False, "message": str(e)}
        setattr(proc, "_demo_flag", demo)
        _monitor_proc = proc
        _append_log(f"[API] 監視開始 pid={proc.pid} demo={demo}")
        _start_log_reader(proc)
    return {"ok": True, "pid": proc.pid, "demo": demo, "args": args}


@router.post("/monitor/stop")
def monitor_stop() -> dict[str, Any]:
    global _monitor_proc
    with _monitor_lock:
        proc = _monitor_proc
        if proc is None or proc.poll() is not None:
            _monitor_proc = None
            _append_log("[API] 監視停止（プロセスなし）")
            return {"ok": True, "message": "起動中の監視はありませんでした"}
        pid = proc.pid
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        _monitor_proc = None
        _append_log(f"[API] 監視停止 pid={pid}")
    return {"ok": True, "message": f"停止しました pid={pid}"}
