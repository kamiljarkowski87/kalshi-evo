"""Śledzenie wyników — P&L, win rate, Sharpe, drawdown."""
import sqlite3
from datetime import datetime, timedelta
from src.core.logger import log


class PerformanceTracker:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_portfolio_state(self, bankroll: float = 1000.0) -> dict:
        try:
            conn = sqlite3.connect(self.db_path)
            today = datetime.now().date().isoformat()
            cursor = conn.cursor()

            cursor.execute("""SELECT COUNT(*), SUM(pnl_usd),
                SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END),
                SUM(CASE WHEN outcome='LOSS' THEN 1 ELSE 0 END)
                FROM trades WHERE DATE(created_at)=? AND status='closed'""", (today,))
            row = cursor.fetchone()
            conn.close()

            bets = row[0] or 0
            daily_pnl = row[1] or 0.0
            wins = row[2] or 0
            losses = row[3] or 0
        except Exception:
            bets = wins = losses = 0
            daily_pnl = 0.0

        return {
            "bankroll": bankroll,
            "daily_pnl": daily_pnl,
            "daily_loss_limit": -bankroll * 0.05,
            "bets_today": bets,
            "wins_today": wins,
            "losses_today": losses,
        }

    def get_recent_trades(self, hours: int = 24) -> list:
        try:
            conn = sqlite3.connect(self.db_path)
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, status, outcome FROM trades WHERE created_at > ?", (cutoff,))
            rows = cursor.fetchall()
            conn.close()
            return [{"ticker": r[0], "status": r[1], "outcome": r[2]} for r in rows]
        except Exception:
            return []

    def get_summary_30d(self) -> dict:
        try:
            conn = sqlite3.connect(self.db_path)
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            cursor = conn.cursor()
            cursor.execute("""SELECT COUNT(*), SUM(pnl_usd),
                AVG(CASE WHEN outcome='WIN' THEN 1.0 ELSE 0.0 END)
                FROM trades WHERE status='closed' AND created_at > ?""", (cutoff,))
            row = cursor.fetchone()
            conn.close()
            return {"trades_30d": row[0] or 0, "pnl_30d": row[1] or 0.0, "win_rate_30d": row[2] or 0.0}
        except Exception:
            return {"trades_30d": 0, "pnl_30d": 0.0, "win_rate_30d": 0.0}
