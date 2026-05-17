"""Dynamiczny Kelly sizer oparty na historii zakładów per kategoria."""
import sqlite3
from src.core.logger import log


def calculate_dynamic_kelly(
    my_prob: float,
    market_prob: float,
    category: str,
    confidence: str,
    bankroll: float,
    db_path: str,
) -> dict:
    payout = (1 - market_prob) / market_prob if market_prob > 0 else 1
    q = 1 - my_prob
    base_kelly = (my_prob * payout - q) / payout
    half_kelly = max(0, base_kelly * 0.5)

    history_modifier = _get_category_modifier(category, db_path)
    confidence_modifiers = {"very_high": 1.2, "high": 1.0, "medium": 0.7, "low": 0.4}
    conf_modifier = confidence_modifiers.get(confidence, 0.5)

    final_kelly = half_kelly * history_modifier * conf_modifier
    max_pct = 0.03
    min_bet = 1.0

    bet_pct = min(final_kelly, max_pct)
    bet_usd = max(min_bet, bankroll * bet_pct)
    contracts = max(1, int(bet_usd / max(market_prob, 0.01)))

    result = {
        "bet_usd": round(bet_usd, 2),
        "bet_pct": round(bet_pct * 100, 2),
        "contracts": contracts,
        "base_kelly": round(base_kelly, 4),
        "history_modifier": history_modifier,
        "confidence_modifier": conf_modifier,
        "explanation": f"Kelly={base_kelly:.2%} × hist={history_modifier:.1f} × conf={conf_modifier:.1f} = {bet_pct:.2%} bankrollu",
    }
    log.info("kelly.sized", **result, category=category)
    return result


def _get_category_modifier(category: str, db_path: str) -> float:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*),
                   AVG(CASE WHEN outcome='WIN' THEN 1.0 ELSE 0.0 END),
                   AVG(my_prob_at_entry)
            FROM trades
            WHERE category=? AND status='closed'
            AND created_at > datetime('now', '-90 days')
        """, (category,))
        row = cursor.fetchone()
        conn.close()
        count, win_rate, avg_prob = row
        if not count or count < 20:
            return 0.3
        if avg_prob and avg_prob > 0:
            ratio = win_rate / avg_prob
            return max(0.5, min(1.4, ratio))
        return 1.0
    except Exception:
        return 0.3
