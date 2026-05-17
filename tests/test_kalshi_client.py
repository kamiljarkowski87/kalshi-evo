"""Testy KalshiMockClient."""
import sys
sys.path.insert(0, '.')
from src.core.kalshi_client import KalshiMockClient


def test_mock_markets():
    client = KalshiMockClient()
    markets = client.get_markets()
    assert len(markets) > 0
    for m in markets:
        assert 'ticker' in m
        assert 'yes_bid' in m
        assert 'volume_24h' in m


def test_mock_balance():
    client = KalshiMockClient()
    balance = client.get_balance()
    assert balance == 1000.0


def test_mock_order():
    client = KalshiMockClient()
    result = client.place_limit_order("TEST-TICKER", "yes", 50, 10)
    assert 'order' in result
    assert client.get_balance() < 1000.0
