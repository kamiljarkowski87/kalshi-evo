"""
3-rundowa debata między specjalistycznymi agentami.
Syntezer jest oddzielnym agentem — eliminuje groupthink.
"""
import json
import os
import anthropic
from dotenv import load_dotenv
from src.core.logger import log

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

DEBATE_SYSTEM = """Jesteś {role} specjalizującym się w {specialty}.
Szacujesz prawdopodobieństwo zdarzenia na Kalshi prediction market.

ZASADY:
1. Podaj probability jako liczbę 0.0-1.0
2. Max 3 key_factors (krótkie, konkretne)
3. Max 2 data_sources_used
4. uncertainty_note max 1 zdanie
5. NIE daj się przekonać bez nowych faktów

Odpowiedz WYŁĄCZNIE surowym JSON (bez markdown, bez ```):
{{"probability":0.0,"confidence":"high","key_factors":["fakt1","fakt2"],"data_sources_used":["src1"],"uncertainty_note":"uwaga","updated_from_debate":false}}"""

SYNTHESIZER_SYSTEM = """Jesteś niezależnym arbitrem. NIE brałeś udziału w debacie.
Oceniasz jakość argumentów i agreguj wyniki.

ZASADY:
1. Sprawdź czy każdy agent podał KONKRETNE fakty
2. Outlier (>15% od średniej) musi mieć mocne uzasadnienie
3. Wyżej waż agentów z SPECJALIZACJĄ w tej kategorii
4. Spread >25% między agentami → confidence = "low"
5. reasoning max 2 zdania

Odpowiedz WYŁĄCZNIE surowym JSON (bez markdown, bez ```):
{{"final_probability":0.0,"confidence":"high","reasoning":"krótki powód","agent_weights_applied":{{}},"outlier_detected":false,"outlier_agent":null,"debate_quality":"strong","recommendation":"bet"}}"""


def _llm_call(system: str, messages: list, fast: bool = False) -> dict:
    model = "claude-haiku-4-5-20251001" if fast else "claude-sonnet-4-6"
    resp = client.messages.create(
        model=model,
        max_tokens=400,
        system=system,
        messages=messages,
    )
    text = resp.content[0].text.strip()
    # Spróbuj bezpośrednio
    try:
        return json.loads(text)
    except Exception:
        pass
    # Wyczyść markdown code blocks jeśli są
    if "```" in text:
        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    # Znajdź JSON w tekście (od { do ostatniego })
    start = text.find('{')
    end = text.rfind('}') + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except Exception:
            pass
    raise ValueError(f"Nie można sparsować JSON: {text[:200]}")


def _trim_data_package(data: dict, max_chars: int = 800) -> dict:
    """Przycina duże pola tekstowe żeby nie przepalać tokenów."""
    trimmed = {}
    for k, v in data.items():
        if isinstance(v, str) and len(v) > max_chars:
            trimmed[k] = v[:max_chars] + "…"
        elif isinstance(v, dict):
            trimmed[k] = _trim_data_package(v, max_chars)
        else:
            trimmed[k] = v
    return trimmed


def run_debate(market: dict, data_package: dict, agents: list) -> dict:
    trimmed_data = _trim_data_package(data_package)
    context = f"""RYNEK: {market['title']}
PYTANIE: {market.get('yes_sub_title', market['title'])}
AKTUALNA CENA YES: {market['yes_bid']}¢ (rynek szacuje: {market['yes_bid']}% szans)
DEADLINE: {market.get('close_time', 'N/A')[:10]}
VOLUME 24H: ${market.get('volume_24h', 0):,.0f}

ZEBRANE DANE:
{json.dumps(trimmed_data, indent=2, ensure_ascii=False)}"""

    # RUNDA 1 — niezależna analiza
    round1 = {}
    for agent in agents:
        try:
            system = DEBATE_SYSTEM.format(role=agent['role'], specialty=agent['specialty'])
            result = _llm_call(system, [{"role": "user", "content": context}], fast=True)
            round1[agent['name']] = result
            log.info("debate.round1", agent=agent['name'], prob=result.get('probability'))
        except Exception as e:
            log.error("debate.round1_error", agent=agent['name'], error=str(e))
            round1[agent['name']] = {"probability": 0.5, "confidence": "low", "key_factors": [], "data_sources_used": [], "uncertainty_note": str(e), "updated_from_debate": False}

    probs = [r['probability'] for r in round1.values()]
    avg_prob = sum(probs) / len(probs) if probs else 0.5

    # RUNDA 2 — wzajemna weryfikacja
    round2 = {}
    for agent in agents:
        try:
            system = DEBATE_SYSTEM.format(role=agent['role'], specialty=agent['specialty'])
            my_r1 = round1[agent['name']]
            others = {k: v for k, v in round1.items() if k != agent['name']}
            outlier_note = ""
            if abs(my_r1['probability'] - avg_prob) > 0.15:
                outlier_note = f"\nUWAGA: Twoja ocena ({my_r1['probability']:.2f}) odbiega >15% od średniej ({avg_prob:.2f}). Musisz uzasadnić lub zaktualizować."

            update_msg = f"""Twoja ocena z rundy 1: {my_r1['probability']:.2f}
Średnia pozostałych: {avg_prob:.2f}
Odpowiedzi innych agentów: {json.dumps(others, indent=2)}
{outlier_note}
Czy podtrzymujesz ocenę? Jeśli zmieniasz — podaj NOWY konkretny argument.
Odpowiedz w tym samym formacie JSON, ustaw "updated_from_debate": true/false."""

            result = _llm_call(system, [
                {"role": "user", "content": context},
                {"role": "assistant", "content": json.dumps(my_r1)},
                {"role": "user", "content": update_msg},
            ], fast=True)
            round2[agent['name']] = result
            log.info("debate.round2", agent=agent['name'], prob=result.get('probability'), updated=result.get('updated_from_debate'))
        except Exception as e:
            log.error("debate.round2_error", agent=agent['name'], error=str(e))
            round2[agent['name']] = round1[agent['name']]

    # RUNDA 3 — niezależny syntezer
    synthesis_input = f"""RYNEK: {market['title']}
CENA RYNKOWA: {market['yes_bid']}¢

WYNIKI RUNDY 1:
{json.dumps(round1, indent=2)}

WYNIKI RUNDY 2 (po debacie):
{json.dumps(round2, indent=2)}"""

    try:
        synthesis = _llm_call(SYNTHESIZER_SYSTEM, [{"role": "user", "content": synthesis_input}])
    except Exception as e:
        log.error("debate.synthesis_error", error=str(e))
        probs2 = [r['probability'] for r in round2.values()]
        avg2 = sum(probs2) / len(probs2) if probs2 else 0.5
        synthesis = {"final_probability": avg2, "confidence": "low", "reasoning": "Błąd syntezy", "agent_weights_applied": {}, "outlier_detected": False, "outlier_agent": None, "debate_quality": "weak", "recommendation": "skip"}

    market_prob = market['yes_bid'] / 100
    my_prob = synthesis['final_probability']
    edge = my_prob - market_prob

    log.info("debate.done", ticker=market['ticker'], my_prob=my_prob, market_prob=market_prob, edge=edge, quality=synthesis.get('debate_quality'))

    return {
        "market_ticker": market['ticker'],
        "round1": round1,
        "round2": round2,
        "synthesis": synthesis,
        "market_prob": market_prob,
        "my_prob": my_prob,
        "edge": edge,
    }
