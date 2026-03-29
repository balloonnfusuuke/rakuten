"""
TradingView スクリーナー自動操作（Playwright）。
UI が変わるとセレクタ調整が必要。失敗時は空リストを返す。
"""

from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)


async def run_screener(
    screener_url: str = "https://www.tradingview.com/screener/",
    crsi_less_than: float = 10.0,
    headless: bool = True,
) -> List[str]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("playwright が未インストールです。pip install playwright && playwright install chromium")
        return []

    symbols: List[str] = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(screener_url, wait_until="networkidle", timeout=60_000)
            # 以下はサイト構造依存 — 実運用前にセレクタを検証すること
            logger.info("TradingView ページを開きました。フィルター適用は環境に合わせて実装してください。")
            await browser.close()
    except Exception as e:
        logger.exception("TradingView スクレイピング失敗: %s", e)
    return symbols


def run_screener_sync(
    screener_url: str = "https://www.tradingview.com/screener/",
    crsi_less_than: float = 10.0,
    headless: bool = True,
) -> List[str]:
    import asyncio

    return asyncio.run(
        run_screener(
            screener_url=screener_url,
            crsi_less_than=crsi_less_than,
            headless=headless,
        )
    )
