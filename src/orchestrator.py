"""
Kalshi Evo — główna pętla systemu.
Faza 1: skanuj rynki i wyświetlaj top 10 kandydatów.
"""
import schedule
import time
from datetime import datetime

from src.core.config import Config
from src.core.logger import log, setup_logging
from src.core.database import init_db
from src.core.kalshi_client import KalshiClient, KalshiMockClient


def classify_market(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ['rain', 'snow', 'temperature', 'weather', 'hurricane', 'flood']):
        return 'weather'
    if any(w in t for w in ['fed', 'rate', 'inflation', 'cpi', 'gdp', 'jobs', 'unemployment', 'nfp', 'fomc']):
        return 'economics'
    if any(w in t for w in ['nfl', 'nba', 'mlb', 'nhl', 'game', 'match', 'score', 'win', 'playoff', 'championship']):
        return 'sports'
    if any(w in t for w in ['election', 'president', 'congress', 'senate', 'vote', 'poll', 'bill', 'law']):
        return 'politics'
    if any(w in t for w in ['bitcoin', 'btc', 'eth', 'crypto', 'ethereum']):
        return 'crypto'
    return 'other'


def scan_markets(kalshi) -> list[dict]:
    """Pobiera i filtruje rynki Kalshi."""
    all_markets = kalshi.get_markets(status="open", limit=200)

    # Filtruj: płynność >= $5000 i cena w bezpiecznej strefie 15-85¢
    candidates = [
        m for m in all_markets
        if m.get('volume_24h', 0) >= 5000
        and 15 <= m.get('yes_bid', 0) <= 85
    ]

    # Dodaj kategorię
    for m in candidates:
        m['category'] = classify_market(m.get('title', ''))

    # Sortuj po volume
    candidates.sort(key=lambda x: x.get('volume_24h', 0), reverse=True)
    return candidates


def print_top_markets(markets: list[dict], n: int = 10) -> None:
    """Wyświetla top N rynków w czytelnym formacie."""
    print(f"\n{'='*70}")
    print(f"TOP {n} RYNKÓW KALSHI — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*70}")
    print(f"{'#':<3} {'TICKER':<30} {'YES':>4} {'VOL $':>10} {'KAT':<12} {'DEADLINE':<12}")
    print(f"{'-'*70}")

    for i, m in enumerate(markets[:n], 1):
        ticker = m.get('ticker', '')[:28]
        yes_bid = m.get('yes_bid', 0)
        volume = m.get('volume_24h', 0)
        category = m.get('category', 'other')
        deadline = m.get('close_time', '')[:10]

        print(f"{i:<3} {ticker:<30} {yes_bid:>3}¢ {volume:>10,.0f} {category:<12} {deadline}")

    print(f"{'='*70}")
    print(f"Razem kandydatów (vol>$5K, cena 15-85¢): {len(markets)}")
    print()


def main_cycle(kalshi, config: Config) -> None:
    log.info("orchestrator.cycle_start")
    try:
        candidates = scan_markets(kalshi)
        print_top_markets(candidates, n=10)
        log.info("orchestrator.cycle_done", candidates=len(candidates))
    except Exception as e:
        log.error("orchestrator.cycle_error", error=str(e))


def main():
    config = Config()
    setup_logging(config.log_level)
    init_db(config.db_path)

    log.info("kalshi_evo.start", mode=config.trading_mode, env=config.kalshi_env)
    print("\n🤖 KALSHI EVO SYSTEM — START")
    print(f"   Tryb: {config.trading_mode.upper()}")
    print(f"   Środowisko: {config.kalshi_env}")

    # Wybierz client — prawdziwy jeśli są klucze, mock jeśli nie ma
    if config.has_kalshi_keys():
        kalshi = KalshiClient(
            config.kalshi_api_key_id,
            config.kalshi_private_key_path,
            config.kalshi_env,
        )
        print("   Auth: RSA-PSS (prawdziwy klucz)")
    else:
        kalshi = KalshiMockClient()
        print("   Auth: MOCK (brak kluczy RSA — używam przykładowych danych)")

    # Uruchom natychmiast
    main_cycle(kalshi, config)

    # Potem co 5 minut
    schedule.every(5).minutes.do(main_cycle, kalshi=kalshi, config=config)
    log.info("orchestrator.scheduler_running", interval="5min")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
