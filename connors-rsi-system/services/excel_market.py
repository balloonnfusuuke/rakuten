from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# 列名が分からないときの候補（部分一致・大文字小文字無視）
SYMBOL_HEADER_ALIASES: List[str] = [
    "銘柄コード",
    "コード",
    "銘柄",
    "symbol",
    "ticker",
    "ティッカー",
    "銘柄名",
]
PRICE_HEADER_ALIASES: List[str] = [
    "現在値",
    "株価",
    "終値",
    "気配",
    "price",
    "last",
    "最新",
    "値",
    "lastprice",
]
PREV_HEADER_ALIASES: List[str] = [
    "前日終値",
    "前終値",
    "昨收",
    "previous",
    "prev",
    "前日",
]


def normalize_symbol_key(s: Any) -> str:
    """照合用キー（国内株は .T 除去・数値は先頭ゼロ除去）。"""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    t = str(s).strip().upper().replace(" ", "")
    if t.endswith(".T"):
        t = t[:-2]
    t = t.replace(",", "")
    if re.fullmatch(r"\d+\.0+", t):
        t = t.split(".")[0]
    if t.isdigit():
        t = str(int(t))
    return t


def _norm_col_name(c: Any) -> str:
    return str(c).strip().lower().replace(" ", "")


def _find_column(
    df: pd.DataFrame,
    configured: str,
    aliases: List[str],
) -> Optional[str]:
    if df.empty or df.columns is None:
        return None
    cols = list(df.columns)
    cfg = (configured or "").strip()
    if cfg:
        for c in cols:
            if str(c).strip() == cfg:
                return str(c)
        cfg_l = cfg.lower()
        for c in cols:
            if cfg_l == _norm_col_name(c):
                return str(c)
        for c in cols:
            if cfg_l in _norm_col_name(c):
                return str(c)
    for a in aliases:
        al = a.lower()
        for c in cols:
            if al in _norm_col_name(c):
                return str(c)
    return None


def _resolve_excel_path(raw: str, config_parent: Path, project_root: Path) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    if (config_parent / p).is_file():
        return (config_parent / p).resolve()
    return (project_root / p).resolve()


_cache: Dict[str, Any] = {
    "key": "",
    "mtime": -1.0,
    "map": {},
    "err": None,
    "read_mono": 0.0,
}


def _read_excel_raw(
    path: Path,
    sheet: Any,
) -> Tuple[pd.DataFrame, Optional[str]]:
    try:
        df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    except ImportError:
        return pd.DataFrame(), "openpyxl が必要です（pip install openpyxl）"
    except PermissionError:
        return pd.DataFrame(), f"Excel がファイルをロックしています: {path}"
    except FileNotFoundError:
        return pd.DataFrame(), f"ファイルがありません: {path}"
    except Exception as e:
        logger.exception("Excel 読み込み失敗")
        return pd.DataFrame(), str(e)
    return df, None


def read_all_prices_from_excel(
    cfg: dict[str, Any],
    *,
    config_parent: Path,
    project_root: Path,
    force_reload: bool = False,
) -> Tuple[Dict[str, Dict[str, Any]], Optional[str], float, float]:
    """
    戻り値: (symbol_key -> {price, change_pct, name, ...}, error, file_mtime, file_age_sec)
    """
    md = cfg.get("market_data") or {}
    raw_path = (md.get("excel_path") or "").strip()
    if not raw_path:
        return {}, "config の market_data.excel_path を設定してください", 0.0, -1.0

    path = _resolve_excel_path(raw_path, config_parent, project_root)
    if not path.is_file():
        return {}, f"Excel が見つかりません: {path}", 0.0, -1.0

    try:
        mtime = path.stat().st_mtime
    except OSError as e:
        return {}, str(e), 0.0, -1.0

    cache_key = str(path.resolve())
    now_m = time.monotonic()
    if (
        not force_reload
        and _cache["key"] == cache_key
        and _cache["mtime"] == mtime
        and (now_m - float(_cache["read_mono"])) < 0.15
    ):
        age = max(0.0, time.time() - mtime)
        return _cache["map"], _cache["err"], mtime, age

    sheet = md.get("sheet")
    if sheet is None:
        sheet = md.get("sheet_name", 0)

    df, err = _read_excel_raw(path, sheet)
    if err:
        if _cache["map"] and _cache["key"] == cache_key:
            logger.warning("Excel 再読込失敗、キャッシュを使用: %s", err)
            return _cache["map"], err, float(_cache.get("mtime") or mtime), max(
                0.0, time.time() - float(_cache.get("mtime") or mtime)
            )
        return {}, err, mtime, max(0.0, time.time() - mtime)

    sym_col = _find_column(
        df,
        str(md.get("symbol_column") or ""),
        SYMBOL_HEADER_ALIASES,
    )
    price_col = _find_column(
        df,
        str(md.get("price_column") or ""),
        PRICE_HEADER_ALIASES,
    )
    if not sym_col or not price_col:
        return (
            {},
            f"列が特定できません。見つかった列: {list(df.columns)}。"
            f" symbol_column / price_column を config.yaml で指定してください。",
            mtime,
            max(0.0, time.time() - mtime),
        )

    prev_cfg = (md.get("prev_close_column") or "").strip()
    prev_col = _find_column(df, prev_cfg, PREV_HEADER_ALIASES) if prev_cfg else None
    if not prev_col and prev_cfg:
        prev_col = _find_column(df, "", PREV_HEADER_ALIASES)

    out: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        key = normalize_symbol_key(row.get(sym_col))
        if not key:
            continue
        raw_p = row.get(price_col)
        try:
            price = float(pd.to_numeric(raw_p, errors="coerce"))
        except (TypeError, ValueError):
            continue
        if price <= 0 or pd.isna(price):
            continue
        chg = None
        if prev_col and prev_col in row.index:
            try:
                prev = float(pd.to_numeric(row.get(prev_col), errors="coerce"))
                if prev and prev > 0:
                    chg = (price / prev - 1.0) * 100.0
            except (TypeError, ValueError):
                pass
        out[key] = {
            "price": price,
            "change_pct": chg,
            "market_state": "EXCEL",
            "currency": md.get("currency_hint") or "JPY",
            "name": str(row.get(sym_col, key)),
        }

    age = max(0.0, time.time() - mtime)
    _cache.update(
        {
            "key": cache_key,
            "mtime": mtime,
            "map": out,
            "err": None,
            "read_mono": now_m,
        }
    )
    return out, None, mtime, age


def quotes_for_symbols(
    symbols: List[str],
    cfg: dict[str, Any],
    *,
    config_parent: Path,
    project_root: Path,
) -> Dict[str, Any]:
    """API 用: 指定銘柄だけ返す（yfinance 形式に近い dict）。"""
    md = cfg.get("market_data") or {}
    stale_sec = float(md.get("stale_warn_sec", 120))

    full_map, err, mtime, age = read_all_prices_from_excel(
        cfg, config_parent=config_parent, project_root=project_root
    )

    as_of = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat() if mtime else None

    quotes: Dict[str, Any] = {}
    for sym in symbols:
        k = normalize_symbol_key(sym)
        row = full_map.get(k)
        if row:
            quotes[sym.upper()] = {
                "price": row["price"],
                "change_pct": row.get("change_pct"),
                "market_state": row.get("market_state"),
                "currency": row.get("currency"),
                "name": row.get("name"),
            }
        else:
            quotes[sym.upper()] = {
                "price": None,
                "change_pct": None,
                "market_state": None,
                "currency": None,
                "name": None,
                "error": "Excel に該当行なし",
            }

    warn = None
    if stale_sec > 0 and age > stale_sec:
        warn = f"Excel の最終更新から {int(age)} 秒以上経過しています。MarketSpeed 側で保存されているか確認してください。"

    return {
        "quotes": quotes,
        "source": "marketspeed_excel",
        "as_of": as_of,
        "error": err,
        "excel_path": str(
            _resolve_excel_path(
                (md.get("excel_path") or "").strip(), config_parent, project_root
            )
        )
        if (md.get("excel_path") or "").strip()
        else None,
        "file_age_sec": round(age, 1),
        "warning": warn,
    }


def build_excel_price_fetcher(
    config_path: Path,
    *,
    project_root: Path,
) -> Callable[[str], Any]:
    """monitor_loop 用: 各ティックで Excel を読み直す（mtime キャッシュあり）。"""
    from monitor.price_feed import PriceTick

    parent = config_path.parent

    def fetch(symbol: str) -> Optional[Any]:
        from services.ops import load_full_config

        cfg = load_full_config(config_path)
        md = cfg.get("market_data") or {}
        if (md.get("source") or "").lower() != "excel":
            return None
        full_map, err, _, _ = read_all_prices_from_excel(
            cfg, config_parent=parent, project_root=project_root
        )
        if err and not full_map:
            logger.debug("Excel 価格なし %s: %s", symbol, err)
            return None
        k = normalize_symbol_key(symbol)
        row = full_map.get(k)
        if not row:
            return None
        px = float(row["price"])
        return PriceTick(symbol=symbol.strip().upper(), price=px, high=px)

    return fetch
