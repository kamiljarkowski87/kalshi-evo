"""
Kalshi API client z RSA-PSS authentication.

Kalshi wymaga podpisania każdego requestu prywatnym kluczem RSA.
Demo: https://demo-api.kalshi.co/trade-api/v2
Live: https://trading-api.kalshi.com/trade-api/v2
"""
import base64
import time
import uuid
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from src.core.logger import log


class KalshiClient:
    def __init__(self, key_id: str, private_key_path: str, env: str = "demo"):
        self.key_id = key_id
        self.env = env
        self.base_url = (
            "https://demo-api.kalshi.co/trade-api/v2"
            if env == "demo"
            else "https://trading-api.kalshi.com/trade-api/v2"
        )
        self.private_key = None
        if key_id and Path(private_key_path).exists():
            with open(private_key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(), password=None
                )
            log.info("kalshi.auth_loaded", env=env, key_id=key_id[:8] + "...")
        else:
            log.warning("kalshi.no_key", msg="Działam w trybie mock — bez prawdziwego API")

    def _sign_request(self, method: str, path: str) -> dict:
        if not self.private_key:
            return {"Content-Type": "application/json"}
        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}{method.upper()}{path}".encode()
        signature = self.private_key.sign(
            message, padding.PKCS1v15(), hashes.SHA256()
        )
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
            "Content-Type": "application/json",
        }

    def _get(self, path: str) -> dict:
        headers = self._sign_request("GET", path)
        resp = requests.get(f"{self.base_url}{path}", headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        headers = self._sign_request("POST", path)
        resp = requests.post(
            f"{self.base_url}{path}", headers=headers, json=body, timeout=10
        )
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> dict:
        headers = self._sign_request("DELETE", path)
        resp = requests.delete(f"{self.base_url}{path}", headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ── Rynki ────────────────────────────────────────────────────────────────

    def get_markets(self, status: str = "open", limit: int = 200) -> list[dict]:
        path = f"/markets?status={status}&limit={limit}"
        data = self._get(path)
        markets = data.get("markets", [])
        log.info("kalshi.markets_fetched", count=len(markets), status=status)
        return markets

    def get_orderbook(self, ticker: str) -> dict:
        return self._get(f"/markets/{ticker}/orderbook")

    def get_market(self, ticker: str) -> dict:
        return self._get(f"/markets/{ticker}")

    # ── Portfolio ─────────────────────────────────────────────────────────────

    def get_balance(self) -> float:
        data = self._get("/portfolio/balance")
        balance = data.get("balance", 0) / 100  # centsy → dolary
        log.info("kalshi.balance", usd=balance)
        return balance

    def get_positions(self) -> list[dict]:
        return self._get("/portfolio/positions").get("positions", [])

    def get_orders(self, status: str = "resting") -> list[dict]:
        return self._get(f"/portfolio/orders?status={status}").get("orders", [])

    def place_limit_order(
        self,
        ticker: str,
        side: str,
        price_cents: int,
        count: int,
        client_order_id: str = None,
    ) -> dict:
        if client_order_id is None:
            client_order_id = str(uuid.uuid4())
        body = {
            "ticker": ticker,
            "action": "buy",
            "side": side,
            "type": "limit",
            "yes_price": price_cents if side == "yes" else 100 - price_cents,
            "count": count,
            "client_order_id": client_order_id,
        }
        log.info("kalshi.order_placed", ticker=ticker, side=side, price=price_cents, count=count)
        return self._post("/portfolio/orders", body)

    def cancel_order(self, order_id: str) -> dict:
        return self._delete(f"/portfolio/orders/{order_id}")

    def cancel_all_orders(self) -> int:
        orders = self.get_orders()
        cancelled = 0
        for order in orders:
            try:
                self.cancel_order(order["order_id"])
                cancelled += 1
            except Exception as e:
                log.error("kalshi.cancel_failed", order_id=order["order_id"], error=str(e))
        log.info("kalshi.all_cancelled", count=cancelled)
        return cancelled


class KalshiMockClient(KalshiClient):
    """Mock client do testów bez prawdziwych kluczy RSA."""

    MOCK_MARKETS = [
        {"ticker": "WEATHER-NYC-RAIN-2026", "title": "Will it rain in NYC on June 1?",
         "yes_sub_title": "Yes, rain > 0.1 inch", "yes_bid": 35, "yes_ask": 37,
         "volume_24h": 12500, "close_time": "2026-06-01T23:59:00Z",
         "category": "weather", "status": "open"},
        {"ticker": "FED-RATE-JUN-2026", "title": "Will Fed cut rates in June 2026?",
         "yes_sub_title": "Yes, rate cut announced", "yes_bid": 62, "yes_ask": 64,
         "volume_24h": 85000, "close_time": "2026-06-18T18:00:00Z",
         "category": "economics", "status": "open"},
        {"ticker": "NBA-CELTICS-WIN-2026", "title": "Will Celtics win Game 5?",
         "yes_sub_title": "Yes, Celtics win", "yes_bid": 55, "yes_ask": 57,
         "volume_24h": 34000, "close_time": "2026-05-25T02:00:00Z",
         "category": "sports", "status": "open"},
        {"ticker": "CPI-MAY-2026-ABOVE3", "title": "Will CPI May 2026 be above 3%?",
         "yes_sub_title": "Yes, CPI > 3.0%", "yes_bid": 28, "yes_ask": 30,
         "volume_24h": 67000, "close_time": "2026-06-10T12:30:00Z",
         "category": "economics", "status": "open"},
        {"ticker": "BTC-80K-MAY-2026", "title": "Will BTC hit $80K before June?",
         "yes_sub_title": "Yes, BTC >= $80,000", "yes_bid": 45, "yes_ask": 47,
         "volume_24h": 120000, "close_time": "2026-05-31T23:59:00Z",
         "category": "crypto", "status": "open"},
        {"ticker": "SENATE-BILL-PASS", "title": "Will Senate pass the budget bill?",
         "yes_sub_title": "Yes, bill passes", "yes_bid": 38, "yes_ask": 40,
         "volume_24h": 8500, "close_time": "2026-06-15T20:00:00Z",
         "category": "politics", "status": "open"},
        {"ticker": "NFP-MAY-2026-200K", "title": "Will NFP May 2026 beat 200K?",
         "yes_sub_title": "Yes, NFP > 200,000 jobs", "yes_bid": 51, "yes_ask": 53,
         "volume_24h": 43000, "close_time": "2026-06-05T12:30:00Z",
         "category": "economics", "status": "open"},
        {"ticker": "WEATHER-CHI-SNOW", "title": "Will it snow in Chicago in May?",
         "yes_sub_title": "Yes, measurable snow", "yes_bid": 8, "yes_ask": 10,
         "volume_24h": 3200, "close_time": "2026-05-31T23:59:00Z",
         "category": "weather", "status": "open"},
        {"ticker": "EURO-USD-PARITY", "title": "Will EUR/USD reach parity in 2026?",
         "yes_sub_title": "Yes, EUR/USD <= 1.00", "yes_bid": 18, "yes_ask": 20,
         "volume_24h": 29000, "close_time": "2026-12-31T23:59:00Z",
         "category": "economics", "status": "open"},
        {"ticker": "LAKERS-PLAYOFFS", "title": "Will Lakers reach conference finals?",
         "yes_sub_title": "Yes, reach conference finals", "yes_bid": 22, "yes_ask": 24,
         "volume_24h": 18000, "close_time": "2026-05-30T03:00:00Z",
         "category": "sports", "status": "open"},
    ]

    def __init__(self):
        self.key_id = "mock"
        self.env = "mock"
        self.base_url = "mock"
        self.private_key = None
        self._balance = 1000.0
        log.info("kalshi.mock_client", msg="Używam mock client — brak kluczy RSA")

    def get_markets(self, status: str = "open", limit: int = 200) -> list[dict]:
        log.info("kalshi.mock_markets", count=len(self.MOCK_MARKETS))
        return self.MOCK_MARKETS

    def get_balance(self) -> float:
        return self._balance

    def place_limit_order(self, ticker, side, price_cents, count, client_order_id=None):
        cost = count * price_cents / 100
        self._balance -= cost
        order_id = client_order_id or str(uuid.uuid4())
        log.info("kalshi.mock_order", ticker=ticker, side=side, price=price_cents, count=count, cost=cost)
        return {"order": {"order_id": order_id, "ticker": ticker, "status": "resting"}}
