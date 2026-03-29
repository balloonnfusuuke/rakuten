from __future__ import annotations

from datetime import date
from typing import Optional

from watchlist.db import WatchlistDB
from watchlist.models import PositionRow, PositionStatus


class PositionManager:
    def __init__(self, db: WatchlistDB) -> None:
        self.db = db

    def register_screened(
        self,
        symbol: str,
        screened_date: date,
        *,
        target_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        crsi_at_entry: Optional[float] = None,
    ) -> int:
        return self.db.add_watch(
            symbol,
            screened_date,
            target_price=target_price,
            stop_price=stop_price,
            crsi_at_entry=crsi_at_entry,
            status=PositionStatus.WATCHING.value,
        )

    def open_holding(
        self,
        row_id: int,
        entry_price: float,
        entry_d: date,
        shares: int,
        target_price: float,
        stop_price: float,
        crsi_at_entry: Optional[float] = None,
    ) -> None:
        self.db.update_position(
            row_id,
            status=PositionStatus.HOLDING.value,
            entry_price=entry_price,
            entry_date=entry_d,
            shares=shares,
            target_price=target_price,
            stop_price=stop_price,
            peak_price=entry_price,
            crsi_at_entry=crsi_at_entry,
        )

    def open_positions(self) -> list[PositionRow]:
        return self.db.list_by_status(PositionStatus.HOLDING.value)

    def watching(self) -> list[PositionRow]:
        return self.db.list_by_status(PositionStatus.WATCHING.value)
