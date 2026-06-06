"""
Klient Polymarket — pobiera rynki z publicznego API (bez kluczy).
Paper trading: symulujemy zakłady lokalnie, nie wysyłamy prawdziwych transakcji.
"""
import requests
import json
from datetime import datetime, timezone

from src.core.logger import log

GAMMA_API = "https://gamma-api.polymarket.com"


class PolymarketClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "KalshiEvo/1.0"

    def get_markets(self, max_days: int = 30, min_volume_24h: float = 500, limit: int = 200) -> list[dict]:
        """Pobiera aktywne rynki zamykające się w ciągu max_days dni."""
        try:
            resp = self.session.get(
                f"{GAMMA_API}/markets",
                params={"active": "true", "closed": "false", "limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            raw = resp.json()
        except Exception as e:
            log.warning("polymarket.fetch_error", error=str(e))
            return []

        now = datetime.now(timezone.utc)
        results = []

        for m in raw:
            try:
                end_date = m.get("endDate") or m.get("endDateIso", "")
                if not end_date:
                    continue
                close_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                days_left = (close_dt - now).days
                if not (1 <= days_left <= max_days):
                    continue

                vol_24h = float(m.get("volume24hr") or 0)
                if vol_24h < min_volume_24h:
                    continue

                prices = json.loads(m.get("outcomePrices", "[0,1]"))
                yes_price = float(prices[0]) if prices else 0
                yes_bid = round(yes_price * 100)

                if not (10 <= yes_bid <= 90):
                    continue

                results.append({
                    "ticker": m.get("conditionId", m.get("id", ""))[:40],
                    "title": m.get("question", ""),
                    "yes_bid": yes_bid,
                    "yes_ask": yes_bid + 1,
                    "volume_24h": vol_24h,
                    "close_time": end_date,
                    "days_left": days_left,
                    "source": "polymarket",
                    "slug": m.get("slug", ""),
                })
            except Exception:
                continue

        results.sort(key=lambda x: x["volume_24h"], reverse=True)
        log.info("polymarket.markets_fetched", count=len(results), max_days=max_days)
        return results
