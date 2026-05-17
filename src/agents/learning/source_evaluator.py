"""Ocena wiarygodności źródeł danych na podstawie historii."""
import json
import sqlite3
from src.core.logger import log


def evaluate_sources(db_path: str, weights_path: str) -> dict:
    """Analizuje które źródła korelują z wygrywającymi zakładami."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT data_sources_used, outcome FROM trades
            WHERE status='closed' AND data_sources_used IS NOT NULL
            AND created_at > datetime('now', '-90 days')
        """)
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        return {"status": "error", "error": str(e)}

    if len(rows) < 10:
        return {"status": "insufficient_data"}

    source_stats: dict[str, dict] = {}
    for sources_json, outcome in rows:
        try:
            sources = json.loads(sources_json) if sources_json else []
        except Exception:
            sources = []
        won = outcome == "WIN"
        for source in sources:
            if source not in source_stats:
                source_stats[source] = {"wins": 0, "total": 0}
            source_stats[source]["total"] += 1
            if won:
                source_stats[source]["wins"] += 1

    adjustments = {}
    for source, stats in source_stats.items():
        if stats["total"] >= 5:
            win_rate = stats["wins"] / stats["total"]
            # Dobre źródło (>60% win rate) → zwiększ wagę
            # Złe źródło (<40% win rate) → zmniejsz wagę
            if win_rate > 0.60:
                adjustments[source] = min(0.98, win_rate)
            elif win_rate < 0.40:
                adjustments[source] = max(0.20, win_rate)

    if adjustments:
        try:
            with open(weights_path) as f:
                existing = json.load(f)
        except Exception:
            existing = {}
        existing.update(adjustments)
        with open(weights_path, 'w') as f:
            json.dump(existing, f, indent=2)
        log.info("source_evaluator.updated", sources=len(adjustments))

    return {"status": "ok", "sources_analyzed": len(source_stats), "adjustments": adjustments}
