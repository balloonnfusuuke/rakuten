from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.control import router as control_router
from watchlist.db import WatchlistDB


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_cfg() -> dict[str, Any]:
    p = Path(os.environ.get("CONNORS_CONFIG", _root() / "config.yaml"))
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _db() -> WatchlistDB:
    cfg = _load_cfg()
    raw = cfg.get("database", {}).get("path", "data/watchlist.db")
    path = Path(raw)
    if not path.is_absolute():
        path = _root() / path
    return WatchlistDB(path)


class PositionOut(BaseModel):
    id: int | None
    symbol: str
    status: str
    entry_price: float | None
    target_price: float | None
    stop_price: float | None
    peak_price: float | None
    shares: int | None
    screened_date: str | None
    entry_date: str | None
    exit_reason: str | None
    pnl: float | None


app = FastAPI(title="ConnorsRSI Monitor API", version="0.1.0")
app.include_router(control_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "ConnorsRSI Monitor API",
        "endpoints": {
            "health": "/health",
            "positions": "/positions",
            "api_summary": "/api/summary",
            "docs": "/docs",
        },
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/positions", response_model=List[PositionOut])
def list_positions() -> List[PositionOut]:
    db = _db()
    rows = db.all_rows()
    out: List[PositionOut] = []
    for r in rows[:200]:
        out.append(
            PositionOut(
                id=r.id,
                symbol=r.symbol,
                status=r.status,
                entry_price=r.entry_price,
                target_price=r.target_price,
                stop_price=r.stop_price,
                peak_price=r.peak_price,
                shares=r.shares,
                screened_date=r.screened_date.isoformat() if r.screened_date else None,
                entry_date=r.entry_date.isoformat() if r.entry_date else None,
                exit_reason=r.exit_reason,
                pnl=r.pnl,
            )
        )
    return out


def create_app() -> FastAPI:
    return app
