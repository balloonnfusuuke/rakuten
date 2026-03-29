from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Generator, List, Optional

from watchlist.models import PositionRow, PositionStatus


SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    screened_date   TEXT NOT NULL,
    entry_price     REAL,
    entry_date      TEXT,
    shares          INTEGER,
    target_price    REAL,
    stop_price      REAL,
    crsi_at_entry   REAL,
    status          TEXT DEFAULT 'WATCHING',
    exit_price      REAL,
    exit_reason     TEXT,
    exit_date       TEXT,
    pnl             REAL,
    peak_price      REAL,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_watchlist_symbol ON watchlist(symbol);
CREATE INDEX IF NOT EXISTS idx_watchlist_status ON watchlist(status);
"""


class WatchlistDB:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate_schema(conn)

    @staticmethod
    def _migrate_schema(conn: sqlite3.Connection) -> None:
        cur = conn.execute("PRAGMA table_info(watchlist)")
        cols = {row[1] for row in cur.fetchall()}
        if "peak_price" not in cols:
            conn.execute("ALTER TABLE watchlist ADD COLUMN peak_price REAL")

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add_watch(
        self,
        symbol: str,
        screened_date: date,
        *,
        entry_price: Optional[float] = None,
        entry_date: Optional[date] = None,
        shares: Optional[int] = None,
        target_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        crsi_at_entry: Optional[float] = None,
        status: str = PositionStatus.WATCHING.value,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO watchlist (
                    symbol, screened_date, entry_price, entry_date, shares,
                    target_price, stop_price, crsi_at_entry, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol.upper(),
                    screened_date.isoformat(),
                    entry_price,
                    entry_date.isoformat() if entry_date else None,
                    shares,
                    target_price,
                    stop_price,
                    crsi_at_entry,
                    status,
                ),
            )
            return int(cur.lastrowid)

    def update_position(self, row_id: int, **fields: object) -> None:
        if not fields:
            return
        cols = []
        vals: list[object] = []
        for k, v in fields.items():
            if v is None and k in ("entry_date", "exit_date", "screened_date"):
                cols.append(f"{k} = ?")
                vals.append(None)
            elif hasattr(v, "isoformat"):
                cols.append(f"{k} = ?")
                vals.append(v.isoformat())  # type: ignore[union-attr]
            else:
                cols.append(f"{k} = ?")
                vals.append(v)
        vals.append(row_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE watchlist SET {', '.join(cols)} WHERE id = ?",
                vals,
            )

    def close_position(
        self,
        row_id: int,
        exit_price: float,
        exit_reason: str,
        exit_d: date,
        pnl: float,
    ) -> None:
        self.update_position(
            row_id,
            status=PositionStatus.CLOSED.value,
            exit_price=exit_price,
            exit_reason=exit_reason,
            exit_date=exit_d,
            pnl=pnl,
        )

    def list_by_status(self, *statuses: str) -> List[PositionRow]:
        placeholders = ",".join("?" * len(statuses))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM watchlist WHERE status IN ({placeholders}) ORDER BY id",
                statuses,
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def list_open_for_monitor(self) -> List[PositionRow]:
        return self.list_by_status(
            PositionStatus.WATCHING.value,
            PositionStatus.HOLDING.value,
        )

    def get(self, row_id: int) -> Optional[PositionRow]:
        with self._connect() as conn:
            r = conn.execute(
                "SELECT * FROM watchlist WHERE id = ?", (row_id,)
            ).fetchone()
        return self._row_to_model(r) if r else None

    def all_rows(self) -> List[PositionRow]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM watchlist ORDER BY id DESC"
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    @staticmethod
    def _row_to_model(r: sqlite3.Row) -> PositionRow:
        def d(key: str) -> Optional[date]:
            v = r[key]
            if v is None:
                return None
            return date.fromisoformat(str(v))

        def dt(key: str) -> Optional[datetime]:
            v = r[key]
            if v is None:
                return None
            try:
                return datetime.fromisoformat(str(v))
            except ValueError:
                return None

        return PositionRow(
            id=r["id"],
            symbol=r["symbol"],
            screened_date=d("screened_date") or date.today(),
            entry_price=r["entry_price"],
            entry_date=d("entry_date"),
            shares=r["shares"],
            target_price=r["target_price"],
            stop_price=r["stop_price"],
            crsi_at_entry=r["crsi_at_entry"],
            peak_price=r["peak_price"],
            status=r["status"],
            exit_price=r["exit_price"],
            exit_reason=r["exit_reason"],
            exit_date=d("exit_date"),
            pnl=r["pnl"],
            created_at=dt("created_at"),
        )
