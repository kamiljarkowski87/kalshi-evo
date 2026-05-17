"""Testy sanity checker."""
import sys
sys.path.insert(0, '.')
from src.agents.decision.sanity_checker import run_sanity_check


def make_debate(my_prob, market_prob, quality="strong"):
    edge = my_prob - market_prob
    return {
        "my_prob": my_prob,
        "market_prob": market_prob,
        "edge": edge,
        "synthesis": {"debate_quality": quality, "confidence": "high", "outlier_detected": False},
    }


def test_good_bet_passes():
    market = {"ticker": "TEST", "yes_bid": 40, "volume_24h": 10000}
    debate = make_debate(0.55, 0.40)
    portfolio = {"daily_pnl": 0, "daily_loss_limit": -50}
    result = run_sanity_check(market, debate, portfolio, [])
    assert result['passed'] is True
    assert result['recommendation'] == 'BET'


def test_low_volume_fails():
    market = {"ticker": "TEST", "yes_bid": 40, "volume_24h": 1000}
    debate = make_debate(0.55, 0.40)
    portfolio = {"daily_pnl": 0, "daily_loss_limit": -50}
    result = run_sanity_check(market, debate, portfolio, [])
    assert result['passed'] is False
    assert not result['checks']['liquidity']


def test_small_edge_fails():
    market = {"ticker": "TEST", "yes_bid": 50, "volume_24h": 10000}
    debate = make_debate(0.52, 0.50)
    portfolio = {"daily_pnl": 0, "daily_loss_limit": -50}
    result = run_sanity_check(market, debate, portfolio, [])
    assert result['passed'] is False
    assert not result['checks']['sufficient_edge']


def test_daily_limit_fails():
    market = {"ticker": "TEST", "yes_bid": 40, "volume_24h": 10000}
    debate = make_debate(0.55, 0.40)
    portfolio = {"daily_pnl": -100, "daily_loss_limit": -50}
    result = run_sanity_check(market, debate, portfolio, [])
    assert result['passed'] is False
    assert not result['checks']['daily_limit']
