"""Kalibracja prawdopodobieństw — moja prob vs rzeczywistość."""
import sqlite3
from src.core.logger import log


def run_calibration_check(db_path: str) -> dict:
    """Sprawdza czy bot jest dobrze skalibrowany."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT my_prob_at_entry, outcome FROM trades
            WHERE status='closed' AND my_prob_at_entry IS NOT NULL
            AND created_at > datetime('now', '-90 days')
        """)
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        return {"status": "error", "error": str(e)}

    if len(rows) < 10:
        return {"status": "insufficient_data", "count": len(rows)}

    # Podziel na buckety
    buckets = {
        "0.15-0.30": [], "0.30-0.50": [], "0.50-0.70": [], "0.70-0.85": []
    }
    for prob, outcome in rows:
        won = 1.0 if outcome == "WIN" else 0.0
        if 0.15 <= prob < 0.30:
            buckets["0.15-0.30"].append((prob, won))
        elif 0.30 <= prob < 0.50:
            buckets["0.30-0.50"].append((prob, won))
        elif 0.50 <= prob < 0.70:
            buckets["0.50-0.70"].append((prob, won))
        elif 0.70 <= prob <= 0.85:
            buckets["0.70-0.85"].append((prob, won))

    calibration = {}
    for bucket, data in buckets.items():
        if len(data) >= 5:
            avg_pred = sum(p for p, _ in data) / len(data)
            avg_actual = sum(w for _, w in data) / len(data)
            bias = avg_pred - avg_actual
            calibration[bucket] = {
                "count": len(data),
                "avg_predicted": round(avg_pred, 3),
                "avg_actual": round(avg_actual, 3),
                "bias": round(bias, 3),
                "status": "overconfident" if bias > 0.05 else "underconfident" if bias < -0.05 else "ok"
            }

    overall_bias = sum(c.get('bias', 0) for c in calibration.values()) / max(len(calibration), 1)
    log.info("calibration.done", buckets=len(calibration), overall_bias=overall_bias)
    return {"status": "ok", "total_trades": len(rows), "calibration": calibration, "overall_bias": round(overall_bias, 3)}
