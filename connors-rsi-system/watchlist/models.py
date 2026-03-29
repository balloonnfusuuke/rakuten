from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Optional


class PositionStatus(str, Enum):
    WATCHING = "WATCHING"
    HOLDING = "HOLDING"
    CLOSED = "CLOSED"


@dataclass
class PositionRow:
    id: Optional[int]
    symbol: str
    screened_date: date
    entry_price: Optional[float]
    entry_date: Optional[date]
    shares: Optional[int]
    target_price: Optional[float]
    stop_price: Optional[float]
    peak_price: Optional[float]
    crsi_at_entry: Optional[float]
    status: str
    exit_price: Optional[float]
    exit_reason: Optional[str]
    exit_date: Optional[date]
    pnl: Optional[float]
    created_at: Optional[datetime] = None
