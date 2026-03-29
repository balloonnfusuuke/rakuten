from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PriceTick:
    symbol: str
    price: float
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None


class MockPriceFeed:
    """テスト用: 事前に価格をキューしたティックを非同期で返す。"""

    def __init__(self, ticks: List[PriceTick]) -> None:
        self._ticks = list(ticks)
        self._idx = 0

    async def stream(self) -> AsyncIterator[PriceTick]:
        for t in self._ticks:
            yield t
            await asyncio.sleep(0)

    async def subscribe(self, symbols: List[str]) -> None:
        logger.debug("Mock subscribe: %s", symbols)


class PollingPriceFeed:
    """
    価格取得関数を一定間隔で呼び出す簡易フィード。
    fetcher(symbol) -> PriceTick | None
    """

    def __init__(
        self,
        fetcher: Callable[[str], Optional[PriceTick]],
        interval_sec: float = 5.0,
    ) -> None:
        self.fetcher = fetcher
        self.interval_sec = interval_sec
        self._symbols: List[str] = []

    async def subscribe(self, symbols: List[str]) -> None:
        self._symbols = list(symbols)

    async def stream(self) -> AsyncIterator[PriceTick]:
        while True:
            for sym in self._symbols:
                tick = self.fetcher(sym)
                if tick is not None:
                    yield tick
            await asyncio.sleep(self.interval_sec)
