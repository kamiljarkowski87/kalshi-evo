"""Perplexity search — aktualne dane z internetu dla agentów."""
import os
import requests
from dotenv import load_dotenv
from src.core.logger import log

load_dotenv()

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")
API_URL = "https://api.perplexity.ai/chat/completions"

CATEGORY_QUERIES = {
    "economics": [
        "latest Fed interest rate decision and Powell statement",
        "latest CPI inflation data United States",
        "latest NFP jobs report United States",
    ],
    "crypto": [
        "Bitcoin price today and recent trend",
        "crypto market sentiment today",
    ],
    "sports": [
        "NBA latest scores and standings today",
        "NFL latest news injuries",
    ],
    "weather": [
        "NOAA weather forecast United States today",
    ],
    "politics": [
        "latest US political polls approval ratings",
    ],
}


def _search(query: str) -> str:
    if not PERPLEXITY_API_KEY:
        return ""
    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {PERPLEXITY_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": query}],
                "max_tokens": 300,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        log.warning("perplexity.search_error", query=query[:50], error=str(e))
        return ""


def gather_perplexity_data(market_title: str, category: str) -> dict:
    """Zbiera aktualne dane z internetu dla danego rynku."""
    if not PERPLEXITY_API_KEY:
        return {}

    results = {}

    # Zapytanie specyficzne dla rynku
    market_query = f"Latest news and data about: {market_title[:100]}"
    market_data = _search(market_query)
    if market_data:
        results["market_specific_news"] = market_data
        log.info("perplexity.market_search", category=category)

    # Zapytania kategorii
    queries = CATEGORY_QUERIES.get(category, [])
    category_results = []
    for q in queries[:2]:  # max 2 zapytania per kategoria
        data = _search(q)
        if data:
            category_results.append({"query": q, "result": data})

    if category_results:
        results["category_data"] = category_results

    return results
