"""Symulacja zakładów bez prawdziwych pieniędzy."""
import sqlite3
import uuid
from datetime import datetime
from src.core.logger import log


class PaperTrader:
    def __init__(self, config):
        self.db_path = config.db_path
        self._bankroll = config.starting_bankroll
        self._positions: dict[str, dict] = {}

    def get_bankroll(self) -> float:
        return self._bankroll

    def simulate_bet(self, market: dict, debate_result: dict, bet: dict, side: str) -> dict:
        ticker = market['ticker']
        price_cents = market['yes_bid'] if side == 'yes' else 100 - market['yes_bid']
        cost = bet['bet_usd']
        order_id = str(uuid.uuid4())[:8]

        if cost > self._bankroll:
            cost = self._bankroll * 0.5

        self._bankroll -= cost
        self._positions[order_id] = {
            "ticker": ticker,
            "side": side,
            "price_cents": price_cents,
            "contracts": bet['contracts'],
            "cost": cost,
            "opened_at": datetime.now().isoformat(),
        }

        # Zapisz do bazy
        self._log_trade(market, debate_result, bet, side, order_id, cost)
        log.info("paper.bet_placed", ticker=ticker, side=side, cost=cost, bankroll=self._bankroll)
        return {"order_id": order_id, "status": "filled_paper", "cost": cost}

    def _log_trade(self, market, debate, bet, side, order_id, cost):
        import json
        conn = sqlite3.connect(self.db_path)
        sources = list(debate.get('round2', {}).keys())
        conn.execute("""
            INSERT INTO trades (ticker, title, category, side, my_prob_at_entry,
            market_prob_at_entry, edge, price_cents, contracts, bet_usd, bet_pct,
            debate_quality, confidence, data_sources_used, order_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
        """, (
            market['ticker'], market.get('title', ''), market.get('category', ''),
            side, debate.get('my_prob'), debate.get('market_prob'), debate.get('edge'),
            market['yes_bid'] if side == 'yes' else 100 - market['yes_bid'],
            bet['contracts'], bet['bet_usd'], bet['bet_pct'],
            debate.get('synthesis', {}).get('debate_quality'),
            debate.get('synthesis', {}).get('confidence'),
            json.dumps(sources), order_id,
        ))
        conn.commit()
        conn.close()

    def settle_position(self, order_id: str, won: bool) -> float:
        pos = self._positions.get(order_id)
        if not pos:
            return 0.0
        payout = pos['contracts'] * 1.0 if won else 0.0
        pnl = payout - pos['cost']
        self._bankroll += payout
        outcome = "WIN" if won else "LOSS"

        conn = sqlite3.connect(self.db_path)
        conn.execute("""UPDATE trades SET outcome=?, pnl_usd=?, status='closed', closed_at=datetime('now')
                        WHERE order_id=?""", (outcome, pnl, order_id))
        conn.commit()
        conn.close()

        del self._positions[order_id]
        log.info("paper.settled", order_id=order_id, outcome=outcome, pnl=pnl, bankroll=self._bankroll)
        return pnl
