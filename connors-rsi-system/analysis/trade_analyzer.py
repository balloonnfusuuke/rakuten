from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


class TradeAnalyzer:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)

    def close(self) -> None:
        self.conn.close()

    def load_closed_trades(self) -> pd.DataFrame:
        query = """
        SELECT symbol, entry_price, exit_price, entry_date, exit_date,
               exit_reason, crsi_at_entry, shares,
               (exit_price - entry_price) / NULLIF(entry_price, 0) AS return_pct,
               (exit_price - entry_price) * shares AS pnl
        FROM watchlist
        WHERE status = 'CLOSED'
          AND entry_price IS NOT NULL AND exit_price IS NOT NULL
        """
        df = pd.read_sql_query(query, self.conn)
        if df.empty:
            return df
        for col in ("entry_date", "exit_date"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df

    def summary_stats(self, df: pd.DataFrame) -> dict[str, Any]:
        if df.empty:
            return {"total_trades": 0}
        wins = df[df["pnl"] > 0]
        losses = df[df["pnl"] <= 0]
        loss_sum = abs(losses["pnl"].sum())
        pf = wins["pnl"].sum() / loss_sum if loss_sum > 0 else float("inf")
        out: dict[str, Any] = {
            "total_trades": len(df),
            "win_rate": len(wins) / len(df) * 100,
            "avg_win_pct": wins["return_pct"].mean() * 100 if len(wins) else 0,
            "avg_loss_pct": losses["return_pct"].mean() * 100 if len(losses) else 0,
            "profit_factor": float(pf) if pf != float("inf") else None,
            "expected_value": float(df["pnl"].mean()),
        }
        if len(wins) and "exit_date" in df.columns and "entry_date" in df.columns:
            hold = (wins["exit_date"] - wins["entry_date"]).dt.days
            out["avg_hold_days_w"] = float(hold.mean())
        if len(losses) and "exit_date" in df.columns and "entry_date" in df.columns:
            hold_l = (losses["exit_date"] - losses["entry_date"]).dt.days
            out["avg_hold_days_l"] = float(hold_l.mean())
        return out

    def exit_reason_breakdown(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "exit_reason" not in df.columns:
            return pd.DataFrame()
        return (
            df.groupby("exit_reason")
            .agg(
                count=("pnl", "count"),
                win_rate=("pnl", lambda x: (x > 0).mean() * 100),
                avg_pnl=("pnl", "mean"),
                avg_ret=("return_pct", lambda x: x.mean() * 100),
            )
            .round(2)
        )

    def crsi_bucket_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "crsi_at_entry" not in df.columns:
            return pd.DataFrame()
        sub = df.dropna(subset=["crsi_at_entry"])
        if sub.empty:
            return pd.DataFrame()
        sub = sub.copy()
        sub["crsi_bucket"] = pd.cut(
            sub["crsi_at_entry"],
            bins=[0, 2, 5, 10],
            labels=["0-2", "2-5", "5-10"],
        )
        return (
            sub.groupby("crsi_bucket", observed=False)
            .agg(
                count=("pnl", "count"),
                win_rate=("pnl", lambda x: (x > 0).mean() * 100),
                avg_ret=("return_pct", lambda x: x.mean() * 100),
            )
            .round(2)
        )
