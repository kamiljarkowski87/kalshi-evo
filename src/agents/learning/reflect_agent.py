"""Analiza wyników — tygodniowa (zamknięte zakłady) + bieżąca (otwarte pozycje)."""
import json
import os
import sqlite3
import anthropic
from dotenv import load_dotenv
from datetime import datetime, timedelta
from src.core.logger import log

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

REFLECT_SYSTEM = """Jesteś analitykiem wyników trading bota na prediction markets.
Analizujesz zakłady z ostatnich 7 dni i wyciągasz wnioski.

Analizuj:
1. KALIBRACJA: gdy bot mówił X% → ile razy faktycznie wygrał?
2. KATEGORIE: które typy rynków były profitable?
3. BŁĘDY: jakie systematyczne błędy popełniał bot?
4. OKAZJE: jakie rynki pomijał a nie powinien?

Odpowiedz WYŁĄCZNIE w JSON:
{
  "week_summary": {"total_bets": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "total_pnl": 0.0, "best_category": "", "worst_category": ""},
  "calibration_analysis": {"overall_bias": "overconfident|underconfident|well_calibrated", "bias_magnitude": 0.0},
  "lessons": [{"observation": "", "lesson": "", "action": "", "priority": "high|medium|low"}],
  "source_performance": {"best_sources": [], "worst_sources": [], "weight_adjustments": {}},
  "strategy_adjustments": {"increase_exposure": [], "decrease_exposure": [], "new_rules": []}
}"""

OPEN_REFLECT_SYSTEM = """Jesteś analitykiem bota do prediction markets. Analizujesz OTWARTE pozycje
(jeszcze nierozliczone) i oceniasz jakość procesu decyzyjnego — nie wyniki, bo ich nie znamy.

Analizuj:
1. JAKOŚĆ DEBATY: czy agenci dobrze argumentowali? Czy devil_advocate był wystarczająco krytyczny?
2. EDGE: czy szacowany edge (różnica my_prob vs market_prob) był uzasadniony danymi?
3. DYWERSYFIKACJA: czy portfel jest dobrze zdywersyfikowany? Czy nie ma za dużo podobnych zakładów?
4. WZORCE: czy widać wzorce w tym co bot obstawia / pomija?

Odpowiedz WYŁĄCZNIE w JSON:
{
  "process_quality": "good|average|poor",
  "lessons": [{"observation": "", "lesson": "", "action": "", "priority": "high|medium|low"}],
  "portfolio_notes": "",
  "recommended_focus": ""
}"""


def run_weekly_reflection(db_path: str, reflections_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticker, category, my_prob_at_entry, market_prob_at_entry,
               edge, outcome, pnl_usd, data_sources_used, debate_quality
        FROM trades WHERE status='closed' AND closed_at > ?
    """, (week_ago,))
    trades = cursor.fetchall()
    conn.close()

    if len(trades) < 3:
        log.info("reflect.insufficient_data", count=len(trades))
        return {"status": "insufficient_data", "trades_count": len(trades)}

    trades_data = [{"ticker": t[0], "category": t[1], "my_prob": t[2], "market_prob": t[3],
                    "edge": t[4], "outcome": t[5], "pnl": t[6], "sources": t[7], "debate_quality": t[8]}
                   for t in trades]

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=REFLECT_SYSTEM,
        messages=[{"role": "user", "content": f"Przeanalizuj zakłady:\n{json.dumps(trades_data, indent=2)}"}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    reflection = json.loads(text)
    reflection['generated_at'] = datetime.now().isoformat()
    reflection['trades_analyzed'] = len(trades)
    reflection['type'] = 'weekly'

    with open(reflections_path, 'a') as f:
        f.write(json.dumps(reflection, ensure_ascii=False) + '\n')

    log.info("reflect.done", trades=len(trades), pnl=reflection.get('week_summary', {}).get('total_pnl'))
    return reflection


def run_open_position_reflection(db_path: str, reflections_path: str) -> dict:
    """Refleksja na otwartych pozycjach — ocenia jakość procesu, nie wyniki."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticker, title, category, my_prob_at_entry, market_prob_at_entry,
               edge, debate_quality, confidence, data_sources_used, created_at
        FROM trades WHERE status='open'
        ORDER BY created_at DESC LIMIT 20
    """)
    trades = cursor.fetchall()
    conn.close()

    if not trades:
        return {"status": "no_open_trades"}

    trades_data = [
        {"ticker": t[0], "title": t[1], "category": t[2], "my_prob": t[3],
         "market_prob": t[4], "edge": t[5], "debate_quality": t[6],
         "confidence": t[7], "sources": t[8], "opened": t[9][:10]}
        for t in trades
    ]

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=OPEN_REFLECT_SYSTEM,
            messages=[{"role": "user", "content": f"Otwarte pozycje:\n{json.dumps(trades_data, indent=2)}"}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        reflection = json.loads(text)
    except Exception as e:
        log.warning("reflect.open.error", error=str(e))
        return {"status": "error"}

    reflection['generated_at'] = datetime.now().isoformat()
    reflection['open_positions'] = len(trades)
    reflection['type'] = 'open_positions'

    with open(reflections_path, 'a') as f:
        f.write(json.dumps(reflection, ensure_ascii=False) + '\n')

    log.info("reflect.open.done", positions=len(trades),
             quality=reflection.get('process_quality'))
    return reflection


def get_recent_lessons(reflections_path: str, n_weeks: int = 4) -> str:
    try:
        with open(reflections_path) as f:
            lines = f.readlines()
        recent = lines[-n_weeks:] if len(lines) >= n_weeks else lines
        lessons_text = "=== WNIOSKI Z POPRZEDNICH TYGODNI ===\n"
        for line in recent:
            r = json.loads(line)
            lessons_text += f"\n[{r.get('generated_at', '')[:10]}]\n"
            for lesson in r.get('lessons', []):
                if lesson.get('priority') in ['high', 'medium']:
                    lessons_text += f"• {lesson['lesson']}\n  → {lesson['action']}\n"
        return lessons_text
    except Exception:
        return ""
