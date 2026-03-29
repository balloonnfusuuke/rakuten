from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from watchlist.db import WatchlistDB
from watchlist.models import PositionRow

logger = logging.getLogger(__name__)


class OrderManager:
    """
    本番では Alpaca/IB に接続。ここではログ＋DB更新（ペーパー相当）。
    """

    def __init__(self, db: WatchlistDB) -> None:
        self.db = db

    async def market_sell(
        self,
        position: PositionRow,
        reason: str,
        exit_price: float,
        exit_d: Optional[date] = None,
    ) -> None:
        d = exit_d or date.today()
        shares = position.shares or 0
        entry = position.entry_price or 0.0
        pnl = (exit_price - entry) * shares if position.id is not None else 0.0
        logger.info(
            "MARKET_SELL %s @ %.4f reason=%s pnl=%.2f",
            position.symbol,
            exit_price,
            reason,
            pnl,
        )
        if position.id is not None:
            self.db.close_position(position.id, exit_price, reason, d, pnl)

    async def limit_sell(
        self,
        position: PositionRow,
        limit_price: float,
        reason: str,
        exit_d: Optional[date] = None,
    ) -> None:
        await self.market_sell(position, reason, limit_price, exit_d)

    async def partial_sell(
        self,
        position: PositionRow,
        ratio: float,
        reason: str,
        exit_price: float,
    ) -> None:
        shares = position.shares or 0
        part = max(1, int(shares * ratio))
        logger.info(
            "PARTIAL_SELL %s ratio=%.2f shares=%d @ %.4f %s",
            position.symbol,
            ratio,
            part,
            exit_price,
            reason,
        )
        if position.id is not None:
            new_shares = max(0, shares - part)
            entry = position.entry_price or 0.0
            realized = (exit_price - entry) * part
            self.db.update_position(
                position.id,
                shares=new_shares,
                pnl=(position.pnl or 0.0) + realized,
            )
