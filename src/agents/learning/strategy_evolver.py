"""Miesięczny tournament strategii — ewolucja przez natural selection."""
import json
import sqlite3
import statistics
from datetime import datetime, timedelta
from src.core.logger import log

STRATEGY_VARIANTS = {
    "conservative": {"min_edge": 0.08, "min_confidence": "high", "max_position_pct": 0.02, "kelly_multiplier": 0.3},
    "balanced":     {"min_edge": 0.06, "min_confidence": "medium", "max_position_pct": 0.03, "kelly_multiplier": 0.5},
    "aggressive":   {"min_edge": 0.04, "min_confidence": "medium", "max_position_pct": 0.05, "kelly_multiplier": 0.8},
}


def evaluate_strategy(name: str, db_path: str, days: int = 30) -> dict:
    try:
        conn = sqlite3.connect(db_path)
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = conn.cursor()
        cursor.execute("SELECT pnl_usd FROM trades WHERE strategy=? AND status='closed' AND created_at > ?", (name, cutoff))
        pnls = [row[0] for row in cursor.fetchall()]
        conn.close()
        if len(pnls) < 5:
            return {"status": "insufficient_data", "sharpe": None, "trades": len(pnls)}
        avg = statistics.mean(pnls)
        std = statistics.stdev(pnls) if len(pnls) > 1 else 1
        sharpe = (avg / std) * (252 ** 0.5) if std > 0 else 0
        win_rate = len([p for p in pnls if p > 0]) / len(pnls)
        return {"strategy": name, "trades": len(pnls), "win_rate": win_rate, "avg_pnl": avg, "sharpe_ratio": sharpe, "total_pnl": sum(pnls)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def run_monthly_evolution(db_path: str, evolution_log: str) -> dict:
    results = {name: evaluate_strategy(name, db_path) for name in STRATEGY_VARIANTS}
    valid = {k: v for k, v in results.items() if v.get('sharpe_ratio') is not None}
    if not valid:
        return {"status": "no_valid_data", "results": results}

    best = max(valid, key=lambda k: valid[k]['sharpe_ratio'])
    worst = min(valid, key=lambda k: valid[k]['sharpe_ratio'])
    report = {"date": datetime.now().isoformat(), "results": results, "winner": best, "loser": worst}

    with open(evolution_log, 'a') as f:
        f.write(json.dumps(report, ensure_ascii=False) + '\n')

    log.info("evolution.done", winner=best, winner_sharpe=valid[best]['sharpe_ratio'])
    return report
