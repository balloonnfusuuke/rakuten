from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def cmd_monitor(config: Path, demo: bool) -> None:
    from monitor.monitor_service import default_price_fetcher, monitor_loop
    from monitor.price_feed import PriceTick
    from watchlist.db import WatchlistDB
    from watchlist.models import PositionStatus

    import yaml

    with open(config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    db_path = cfg.get("database", {}).get("path", "data/watchlist.db")
    p = Path(db_path)
    if not p.is_absolute():
        p = ROOT / p
    db = WatchlistDB(p)

    if demo:
        from services.ops import seed_demo_holding

        info = seed_demo_holding(config_path=config)
        logging.info("デモポジション: %s", info)

        prices = {}
        for r in db.list_by_status(PositionStatus.HOLDING.value):
            if r.target_price:
                prices[r.symbol] = float(r.target_price) * 1.001
            elif r.entry_price:
                prices[r.symbol] = float(r.entry_price) * 1.05
            else:
                prices[r.symbol] = 100.0

        def fetch(sym: str):
            px = prices.get(sym.upper(), 100.0)
            return PriceTick(symbol=sym.upper(), price=px, high=px)

        asyncio.run(monitor_loop(config, price_fetcher=fetch))
    else:
        asyncio.run(monitor_loop(config))


def cmd_screen(config: Path, symbols: str | None) -> None:
    import yaml

    from screener.scheduler import demo_register_symbols_from_list
    from screener.tradingview_scraper import run_screener_sync
    from services.ops import add_screen_symbols

    with open(config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    db_path = cfg.get("database", {}).get("path", "data/watchlist.db")
    p = Path(db_path)
    if not p.is_absolute():
        p = ROOT / p

    if symbols:
        syms = [s.strip() for s in symbols.split(",") if s.strip()]
        add_screen_symbols([s.upper() for s in syms], config_path=config)
        logging.info("手動登録: %s", syms)
        return

    url = cfg.get("screener", {}).get(
        "tradingview_screener_url", "https://www.tradingview.com/screener/"
    )
    out = run_screener_sync(screener_url=url)
    if out:
        demo_register_symbols_from_list(out, str(p))
    else:
        logging.warning(
            "TradingView から銘柄を取得できませんでした。"
            " --symbols AAPL,MSFT のように手動指定してください。"
        )


def cmd_analyze(config: Path) -> None:
    import yaml

    from analysis.trade_analyzer import TradeAnalyzer

    with open(config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    db_path = cfg.get("database", {}).get("path", "data/watchlist.db")
    p = Path(db_path)
    if not p.is_absolute():
        p = ROOT / p
    ta = TradeAnalyzer(p)
    try:
        df = ta.load_closed_trades()
        print(ta.summary_stats(df))
        print(ta.exit_reason_breakdown(df))
    finally:
        ta.close()


def cmd_report(config: Path, out: Path) -> None:
    import yaml

    from analysis.report_generator import build_weekly_report_html

    with open(config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    db_path = cfg.get("database", {}).get("path", "data/watchlist.db")
    p = Path(db_path)
    if not p.is_absolute():
        p = ROOT / p
    html = build_weekly_report_html(p)
    out.write_text(html, encoding="utf-8")
    logging.info("レポート出力: %s", out)


def cmd_api(config: Path, host: str, port: int) -> None:
    import os

    os.environ["CONNORS_CONFIG"] = str(config.resolve())
    import uvicorn

    uvicorn.run(
        "api.server:app",
        host=host,
        port=port,
        reload=False,
        factory=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ConnorsRSI(2) 自動監視システム")
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config.yaml",
        help="config.yaml パス",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mon = sub.add_parser("monitor", help="リアルタイム監視ループ")
    p_mon.add_argument(
        "--demo",
        action="store_true",
        help="デモ用ポジションと目標到達価格で動作確認",
    )

    p_sc = sub.add_parser("screen", help="スクリーナー / 手動ウォッチ登録")
    p_sc.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="カンマ区切り銘柄（例: AAPL,MSFT）",
    )

    sub.add_parser("analyze", help="クローズ済みトレード分析")

    p_rep = sub.add_parser("report", help="HTML週次レポート")
    p_rep.add_argument(
        "-o",
        type=Path,
        default=ROOT / "data" / "weekly_report.html",
    )

    p_api = sub.add_parser("api", help="REST API (FastAPI)")
    p_api.add_argument("--host", default="127.0.0.1")
    p_api.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    cfg_path: Path = args.config

    if args.cmd == "monitor":
        cmd_monitor(cfg_path, args.demo)
    elif args.cmd == "screen":
        cmd_screen(cfg_path, args.symbols)
    elif args.cmd == "analyze":
        cmd_analyze(cfg_path)
    elif args.cmd == "report":
        args.o.parent.mkdir(parents=True, exist_ok=True)
        cmd_report(cfg_path, args.o)
    elif args.cmd == "api":
        cmd_api(cfg_path, args.host, args.port)


if __name__ == "__main__":
    main()
