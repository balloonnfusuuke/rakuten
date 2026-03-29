from __future__ import annotations

from watchlist.models import PositionRow


def target_hit_message(
    pos: PositionRow, price: float, crsi_before: float | None, crsi_after: float | None
) -> str:
    tgt = pos.target_price or 0.0
    return (
        f"【目標到達】{pos.symbol} @ ${price:.2f}  目標: ${tgt:.2f}\n"
        f"ConnorsRSI: {crsi_before} → {crsi_after}"
    )


def stop_loss_message(pos: PositionRow, price: float) -> str:
    sp = pos.stop_price or 0.0
    return f"【損切り】{pos.symbol} @ ${price:.2f}  ストップ: ${sp:.2f}"


def rally_message(pos: PositionRow, price: float, pct_label: str) -> str:
    return f"【騰落アラート】{pos.symbol} @ ${price:.2f}  {pct_label}（手動判断）"
