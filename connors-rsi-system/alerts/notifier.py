from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class AlertNotifier:
    def __init__(
        self,
        line_token: str = "",
        slack_webhook: str = "",
    ) -> None:
        self.line_token = line_token
        self.slack_webhook = slack_webhook

    async def line_notify(self, message: str) -> None:
        if not self.line_token:
            logger.debug("LINE Notify スキップ（トークンなし）: %s", message[:80])
            return
        url = "https://notify-api.line.me/api/notify"
        headers = {"Authorization": f"Bearer {self.line_token}"}
        data = {"message": message}
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(url, headers=headers, data=data)
            r.raise_for_status()

    async def slack(self, text: str, **kwargs: Any) -> None:
        if not self.slack_webhook:
            logger.debug("Slack スキップ（Webhook なし）: %s", text[:80])
            return
        payload: dict[str, Any] = {"text": text, **kwargs}
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(self.slack_webhook, json=payload)
            r.raise_for_status()

    async def alert(self, title: str, body: str, important: bool = False) -> None:
        text = f"*{title}*\n{body}"
        await self.slack(text)
        if important and self.line_token:
            await self.line_notify(f"{title}\n{body}")
