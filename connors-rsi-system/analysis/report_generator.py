from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from analysis.trade_analyzer import TradeAnalyzer


def build_weekly_report_html(db_path: str | Path) -> str:
    ta = TradeAnalyzer(db_path)
    try:
        df = ta.load_closed_trades()
        summary = ta.summary_stats(df)
        br = ta.exit_reason_breakdown(df)
        crsi = ta.crsi_bucket_analysis(df)
    finally:
        ta.close()

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = [
        "<html><head><meta charset='utf-8'><title>週次レポート</title></head><body>",
        f"<h1>ConnorsRSI 週次レポート</h1><p>生成: {now}</p>",
        "<h2>サマリー</h2><pre>",
        repr(summary),
        "</pre><h2>出口理由</h2><pre>",
        br.to_string() if not br.empty else "(データなし)",
        "</pre><h2>CRSIバケット</h2><pre>",
        crsi.to_string() if not crsi.empty else "(データなし)",
        "</pre></body></html>",
    ]
    return "\n".join(parts)
