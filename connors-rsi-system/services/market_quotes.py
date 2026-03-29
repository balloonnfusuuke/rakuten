from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

import httpx

from services.excel_market import quotes_for_symbols
from services.ops import load_config_path, load_full_config, project_root


def _fi_get(fi: Any, key: str) -> Any:
    if fi is None:
        return None
    if isinstance(fi, dict):
        return fi.get(key)
    return getattr(fi, key, None)


def _quotes_via_yfinance(symbols: list[str]) -> tuple[dict[str, Any], Optional[str]]:
    try:
        import yfinance as yf
    except ImportError:
        return {}, "yfinance が未インストールです（pip install yfinance）"

    quotes: dict[str, Any] = {}
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            fi = getattr(t, "fast_info", None)
            price = _fi_get(fi, "last_price") or _fi_get(fi, "regular_market_price")
            chg = _fi_get(fi, "regular_market_change_percent")
            if price is None:
                hist = t.history(period="5d")
                if hist is not None and not hist.empty and "Close" in hist.columns:
                    price = float(hist["Close"].iloc[-1])
            quotes[sym] = {
                "price": float(price) if price is not None else None,
                "change_pct": float(chg) if chg is not None else None,
                "market_state": _fi_get(fi, "market_state"),
                "currency": _fi_get(fi, "currency"),
                "name": sym,
            }
        except Exception as e:
            quotes[sym] = {
                "price": None,
                "change_pct": None,
                "market_state": None,
                "currency": None,
                "name": None,
                "error": str(e),
            }
    return quotes, None


def _quotes_via_yahoo_http(symbols: list[str]) -> tuple[dict[str, Any], Optional[str]]:
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                "https://query1.finance.yahoo.com/v7/finance/quote",
                params={"symbols": ",".join(symbols)},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (compatible; ConnorsRSI-Dashboard/1.0)"
                },
            )
            r.raise_for_status()
            payload = r.json()
    except Exception as e:
        return {}, str(e)
    quotes: dict[str, Any] = {}
    for item in payload.get("quoteResponse", {}).get("result") or []:
        sym = item.get("symbol")
        if not sym:
            continue
        quotes[str(sym)] = {
            "price": item.get("regularMarketPrice"),
            "change_pct": item.get("regularMarketChangePercent"),
            "market_state": item.get("marketState"),
            "currency": item.get("currency"),
            "name": item.get("shortName") or item.get("longName"),
        }
    return quotes, None


def fetch_market_quotes(
    symbols: List[str],
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    """
    market_data.source が excel のとき MarketSpeed 連携 Excel、それ以外は yfinance。
    """
    clean = list(dict.fromkeys(s for s in symbols if s))
    as_of = datetime.now(timezone.utc).isoformat()
    if not clean:
        return {"quotes": {}, "source": "none", "as_of": as_of, "error": None}

    clean = clean[:80]
    p = config_path or load_config_path()
    cfg = load_full_config(p)
    root = project_root()
    md = cfg.get("market_data") or {}
    src = (md.get("source") or "yfinance").strip().lower()

    if src == "excel":
        out = quotes_for_symbols(clean, cfg, config_parent=p.parent, project_root=root)
        out.setdefault("as_of", out.get("as_of") or as_of)
        return out

    quotes, err = _quotes_via_yfinance(clean)
    source = "yfinance_delayed"
    if err or not any(q.get("price") is not None for q in quotes.values()):
        http_q, http_err = _quotes_via_yahoo_http(clean)
        if http_q and any(q.get("price") is not None for q in http_q.values()):
            quotes = http_q
            source = "yahoo_http_delayed"
            err = None
        elif http_err and not err:
            err = http_err

    return {
        "quotes": {k.upper(): v for k, v in quotes.items()},
        "source": source,
        "as_of": as_of,
        "error": err,
        "warning": None,
        "excel_path": None,
        "file_age_sec": None,
    }


def market_source_info(config_path: Optional[Path] = None) -> dict[str, Any]:
    p = config_path or load_config_path()
    cfg = load_full_config(p)
    md = cfg.get("market_data") or {}
    src = (md.get("source") or "yfinance").strip().lower()
    out: dict[str, Any] = {
        "source": src,
        "excel_path_configured": bool((md.get("excel_path") or "").strip()),
        "excel_resolved_path": None,
        "excel_exists": False,
        "excel_mtime_iso": None,
        "file_age_sec": None,
        "last_read_error": None,
    }
    if src != "excel":
        return out
    from services.excel_market import _resolve_excel_path, read_all_prices_from_excel

    raw = (md.get("excel_path") or "").strip()
    if not raw:
        out["last_read_error"] = "excel_path 未設定"
        return out
    path = _resolve_excel_path(raw, p.parent, project_root())
    out["excel_resolved_path"] = str(path)
    out["excel_exists"] = path.is_file()
    if path.is_file():
        try:
            import time

            mtime = path.stat().st_mtime
            out["excel_mtime_iso"] = datetime.fromtimestamp(
                mtime, tz=timezone.utc
            ).isoformat()
            out["file_age_sec"] = round(max(0.0, time.time() - mtime), 1)
        except OSError:
            pass
    _, err, _, age = read_all_prices_from_excel(
        cfg, config_parent=p.parent, project_root=project_root()
    )
    out["last_read_error"] = err
    if age >= 0:
        out["file_age_sec"] = round(age, 1)
    return out
