"""
Kalshi Evo — główna pętla systemu.
Skanuje rynki co 5 minut, uruchamia debatę agentów i składa zakłady.
"""
import json
import schedule
import time
from datetime import datetime, timedelta

from src.core.config import Config
from src.core.logger import log, setup_logging
from src.core.database import init_db
from src.core.kalshi_client import KalshiClient, KalshiMockClient
from src.data.perplexity_search import gather_perplexity_data
from src.agents.debate.debate_engine import run_debate
from src.agents.decision.sanity_checker import run_sanity_check
from src.agents.risk.kelly_sizer import calculate_dynamic_kelly
from src.agents.risk.risk_manager import RiskManager
from src.agents.learning.reflect_agent import run_weekly_reflection, run_open_position_reflection, get_recent_lessons
from src.agents.learning.strategy_evolver import run_monthly_evolution
from src.agents.learning.calibrator import run_calibration_check
from src.agents.learning.source_evaluator import evaluate_sources
from src.execution.paper_trader import PaperTrader
from src.monitoring.telegram_bot import TelegramReporter
from src.monitoring.performance_tracker import PerformanceTracker

# Agenci specjaliści per kategoria
SPECIALIST_AGENTS = {
    "weather": [
        {"name": "noaa_analyst",       "role": "analityk pogodowy NOAA",     "specialty": "meteorologia i modele pogodowe"},
        {"name": "historical_weather", "role": "analityk historii pogody",    "specialty": "historyczne dane opadów i temperatury"},
        {"name": "climate_context",    "role": "analityk klimatu",            "specialty": "sezonowość i anomalie klimatyczne"},
    ],
    "economics": [
        {"name": "fed_watcher",         "role": "analityk polityki Fed",         "specialty": "decyzje FOMC, dot plot, komunikaty Fed"},
        {"name": "macro_data",          "role": "analityk danych makro",         "specialty": "CPI, PCE, NFP, GDP — dane BLS i FRED"},
        {"name": "market_expectations", "role": "analityk oczekiwań rynkowych",  "specialty": "Fed futures, swap rates, Bloomberg survey"},
    ],
    "sports": [
        {"name": "stats_analyst",      "role": "analityk statystyk sportowych", "specialty": "historical performance, head-to-head, recent form"},
        {"name": "injury_scout",       "role": "analityk kontuzji i składu",    "specialty": "injury reports, lineup changes, travel fatigue"},
        {"name": "situational",        "role": "analityk sytuacyjny",           "specialty": "home/away splits, pressure situations, motivation"},
    ],
    "politics": [
        {"name": "polling_analyst",    "role": "analityk sondaży",             "specialty": "agregacja sondaży, historyczna trafność"},
        {"name": "political_historian","role": "historyk polityczny",           "specialty": "historyczne precedensy i base rates"},
        {"name": "sentiment_reader",   "role": "analityk sentymentu",          "specialty": "media coverage, social sentiment trends"},
    ],
    "crypto": [
        {"name": "onchain_analyst",    "role": "analityk on-chain",            "specialty": "metryki blockchain, whale movements, exchange flows"},
        {"name": "technical_crypto",   "role": "analityk techniczny crypto",   "specialty": "RSI, MACD, support/resistance, volume"},
        {"name": "macro_crypto",       "role": "analityk makro-crypto",        "specialty": "korelacja z S&P500, DXY, Fed policy"},
    ],
}
GENERALIST_AGENTS = [
    {"name": "generalist_1", "role": "analityk generalny",   "specialty": "probabilistic reasoning i base rates"},
    {"name": "generalist_2", "role": "analityk krytyczny",   "specialty": "szukanie kontrargumentów i ryzyk"},
    {"name": "devil_advocate","role": "adwokat diabła",      "specialty": "zawsze szuka powodów żeby NIE obstawiać"},
]

SPECIALIST_AGENTS["ai_tech"] = [
    {"name": "ai_industry_analyst", "role": "analityk branży AI",        "specialty": "rynek AI, OpenAI, Anthropic, Google DeepMind, startupy AI, rundy finansowania, IPO"},
    {"name": "tech_ipo_analyst",    "role": "analityk IPO i wycen tech", "specialty": "wyceny spółek technologicznych, historia IPO, rynki prywatne vs publiczne"},
    {"name": "devil_advocate",      "role": "adwokat diabła",            "specialty": "zawsze szuka powodów żeby NIE obstawiać"},
]


def classify_market(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ['rain', 'snow', 'temperature', 'weather', 'hurricane', 'flood', 'storm']):
        return 'weather'
    if any(w in t for w in ['fed', 'rate', 'inflation', 'cpi', 'gdp', 'jobs', 'unemployment', 'nfp', 'fomc', 'ecb', 'recession']):
        return 'economics'
    if any(w in t for w in ['nfl', 'nba', 'mlb', 'nhl', 'game', 'match', 'score', 'win', 'playoff', 'championship', 'super bowl']):
        return 'sports'
    if any(w in t for w in ['election', 'president', 'congress', 'senate', 'vote', 'poll', 'bill', 'law', 'governor']):
        return 'politics'
    if any(w in t for w in ['bitcoin', 'btc', 'eth', 'crypto', 'ethereum', 'solana']):
        return 'crypto'
    if any(w in t for w in ['openai', 'anthropic', 'deepmind', 'ipo', 'ai company', 'artificial intelligence', 'llm', 'gpt', 'claude']):
        return 'ai_tech'
    return 'other'


def gather_data_for_market(market: dict, category: str, config: Config) -> dict:
    """Zbiera dane zewnętrzne dla rynku (Faza 1: podstawowe dane)."""
    data = {
        "market_title": market['title'],
        "category": category,
        "current_market_prob": market['yes_bid'] / 100,
        "volume_24h": market.get('volume_24h', 0),
        "deadline": market.get('close_time', '')[:10],
    }

    # NewsAPI jeśli dostępne
    if config.news_api_key:
        try:
            from newsapi import NewsApiClient
            api = NewsApiClient(api_key=config.news_api_key)
            query = market['title'][:50]
            articles = api.get_everything(q=query, language='en', page_size=5, sort_by='publishedAt')
            data['recent_news'] = [
                {"title": a['title'], "source": a['source']['name'], "date": a['publishedAt'][:10]}
                for a in articles.get('articles', [])[:5]
            ]
        except Exception as e:
            data['recent_news'] = []
            log.warning("data.news_error", error=str(e))
    else:
        data['recent_news'] = []

    # Perplexity — aktualne dane z internetu
    perplexity_data = gather_perplexity_data(market['title'], category)
    if perplexity_data:
        data['live_research'] = perplexity_data
        log.info("data.perplexity_ok", ticker=market['ticker'], keys=list(perplexity_data.keys()))

    return data


def scan_markets(kalshi) -> list[dict]:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    all_markets = kalshi.get_markets(status="open", limit=500)
    candidates = []
    for m in all_markets:
        if m.get('volume_24h', 0) < 100:
            continue
        if not (15 <= m.get('yes_bid', 0) <= 85):
            continue
        close_time = m.get('close_time', '')
        if close_time:
            try:
                close_dt = datetime.fromisoformat(close_time.replace('Z', '+00:00'))
                days_left = (close_dt - now).days
                if days_left > 90 or days_left < 1:
                    continue
            except Exception:
                pass
        candidates.append(m)
    for m in candidates:
        m['category'] = classify_market(m.get('title', ''))
    candidates.sort(key=lambda x: x.get('volume_24h', 0), reverse=True)
    return candidates


def print_top_markets(markets: list[dict], n: int = 10) -> None:
    print(f"\n{'='*70}")
    print(f"TOP {n} RYNKÓW KALSHI — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*70}")
    print(f"{'#':<3} {'TICKER':<30} {'YES':>4} {'VOL $':>10} {'KAT':<12} {'DEADLINE'}")
    print(f"{'-'*70}")
    for i, m in enumerate(markets[:n], 1):
        print(f"{i:<3} {m.get('ticker','')[:28]:<30} {m.get('yes_bid',0):>3}¢ "
              f"{m.get('volume_24h',0):>10,.0f} {m.get('category',''):<12} {m.get('close_time','')[:10]}")
    print(f"{'='*70}\nRazem kandydatów: {len(markets)}\n")


def main_cycle(kalshi, config: Config, trader: PaperTrader, risk_mgr: RiskManager,
               reporter: TelegramReporter, tracker: PerformanceTracker,
               markets_scanned_counter: list) -> None:
    log.info("orchestrator.cycle_start")

    if risk_mgr.is_halted():
        log.warning("orchestrator.halted", msg="Dzienny limit strat osiągnięty")
        return

    candidates = scan_markets(kalshi)
    print_top_markets(candidates, 10)
    markets_scanned_counter[0] += len(candidates)

    recent_lessons = get_recent_lessons(config.reflections_path)
    portfolio = tracker.get_portfolio_state(trader.get_bankroll())
    recent_trades = tracker.get_recent_trades(hours=24)

    # Analizuj max 5 kandydatów per cykl (oszczędność tokenów)
    for market in candidates[:5]:
        try:
            category = market.get('category', 'other')
            agents = SPECIALIST_AGENTS.get(category, GENERALIST_AGENTS)
            data = gather_data_for_market(market, category, config)
            if recent_lessons:
                data['lessons_from_history'] = recent_lessons

            # Debata agentów
            debate = run_debate(market, data, agents)

            # Sanity check
            sanity = run_sanity_check(market, debate, portfolio, recent_trades)
            if not sanity['passed']:
                log.info("orchestrator.skip", ticker=market['ticker'], reasons=sanity['reasons'])
                continue

            # Sizing
            bet = calculate_dynamic_kelly(
                my_prob=debate['my_prob'],
                market_prob=debate['market_prob'],
                category=category,
                confidence=debate['synthesis'].get('confidence', 'medium'),
                bankroll=trader.get_bankroll(),
                db_path=config.db_path,
            )

            if bet['bet_usd'] < 1.0:
                continue

            side = "yes" if debate['edge'] > 0 else "no"
            result = trader.simulate_bet(market, debate, bet, side)
            reporter.send_trade_entry(market, debate, bet, side)
            log.info("orchestrator.bet_placed", ticker=market['ticker'], side=side, bet_usd=bet['bet_usd'])

        except Exception as e:
            log.error("orchestrator.market_error", ticker=market.get('ticker'), error=str(e))
            continue

    log.info("orchestrator.cycle_done", candidates=len(candidates))


def check_and_settle_positions(kalshi, trader: PaperTrader, reporter: TelegramReporter) -> None:
    """Sprawdza otwarte zakłady i rozstrzyga te, które Kalshi już zamknął."""
    import sqlite3
    conn = sqlite3.connect(trader.db_path)
    cur = conn.cursor()
    cur.execute("SELECT order_id, ticker, side, title FROM trades WHERE status='open'")
    open_trades = cur.fetchall()
    conn.close()

    if not open_trades:
        return

    settled = 0
    for order_id, ticker, side, title in open_trades:
        try:
            data = kalshi.get_market(ticker)
            market = data.get('market', data)
            status = market.get('status', '')
            if status not in ('finalized', 'settled', 'resolved', 'determined'):
                continue
            result = market.get('result', '')
            if not result:
                continue
            won = (side == 'yes' and result == 'yes') or (side == 'no' and result == 'no')
            pnl = trader.settle_position(order_id, won)
            settled += 1
            log.info("settle.done", ticker=ticker, side=side, result=result, won=won, pnl=pnl)
            emoji = "✅" if won else "❌"
            reporter.send(
                f"{emoji} *Zakład rozstrzygnięty*\n"
                f"📌 {title or ticker}\n"
                f"Strona: {side.upper()} | Wynik rynku: {result.upper()}\n"
                f"P&L: ${pnl:+.2f}\n"
                f"Bankroll: ${trader.get_bankroll():.2f}"
            )
        except Exception as e:
            log.warning("settle.error", ticker=ticker, error=str(e))

    if settled > 0:
        log.info("settle.batch_done", settled=settled)


def send_daily_report(trader: PaperTrader, tracker: PerformanceTracker,
                      reporter: TelegramReporter, markets_scanned: list) -> None:
    stats = tracker.get_portfolio_state(trader.get_bankroll())
    stats['markets_scanned'] = markets_scanned[0]
    reporter.send_daily_report(stats)
    markets_scanned[0] = 0
    log.info("orchestrator.daily_report_sent")


def run_weekly_jobs(config: Config, reporter: TelegramReporter) -> None:
    reflection = run_weekly_reflection(config.db_path, config.reflections_path)
    if reflection.get('status') != 'insufficient_data':
        reporter.send_weekly_reflection(reflection)
    calibration = run_calibration_check(config.db_path)
    evaluate_sources(config.db_path, config.source_weights_path)
    log.info("orchestrator.weekly_done", calibration_bias=calibration.get('overall_bias'))


def run_monthly_jobs(config: Config) -> None:
    run_monthly_evolution(config.db_path, "./logs/evolution.log")
    log.info("orchestrator.monthly_done")


def main():
    config = Config()
    setup_logging(config.log_level)
    init_db(config.db_path)

    reporter = TelegramReporter(config.telegram_bot_token, config.telegram_chat_id)
    risk_mgr = RiskManager(config)
    tracker = PerformanceTracker(config.db_path)
    trader = PaperTrader(config)
    trader.restore_open_positions()
    markets_scanned = [0]
    cycle_counter = [0]

    print("\n🤖 KALSHI EVO SYSTEM — START")
    print(f"   Tryb: {config.trading_mode.upper()}")
    print(f"   Środowisko Kalshi: {config.kalshi_env}")
    print(f"   Bankroll: ${config.starting_bankroll:,.2f}")

    if config.has_kalshi_keys():
        kalshi = KalshiClient(config.kalshi_api_key_id, config.kalshi_private_key_path, config.kalshi_env)
        print("   Auth: RSA-PSS (prawdziwy klucz)")
    else:
        kalshi = KalshiMockClient()
        print("   Auth: MOCK (brak kluczy RSA)")

    reporter.send("🤖 *Kalshi Evo System uruchomiony*\nTryb: paper trading\nSkanowanie co 5 minut\nBankroll: $" + str(config.starting_bankroll))

    def main_cycle_with_learning(**kwargs):
        main_cycle(**kwargs)
        cycle_counter[0] += 1
        # Co 12 cykli (~1h) sprawdź wyniki zakładów i refleksja
        if cycle_counter[0] % 12 == 0:
            log.info("reflect.open.trigger", cycle=cycle_counter[0])
            check_and_settle_positions(kalshi, trader, reporter)
            run_open_position_reflection(config.db_path, config.reflections_path)

    # Uruchom natychmiast
    main_cycle_with_learning(kalshi=kalshi, config=config, trader=trader,
                             risk_mgr=risk_mgr, reporter=reporter, tracker=tracker,
                             markets_scanned_counter=markets_scanned)

    # Harmonogram
    schedule.every(5).minutes.do(main_cycle_with_learning, kalshi=kalshi, config=config, trader=trader,
                                  risk_mgr=risk_mgr, reporter=reporter, tracker=tracker,
                                  markets_scanned_counter=markets_scanned)
    schedule.every(1).hours.do(check_and_settle_positions, kalshi=kalshi, trader=trader, reporter=reporter)
    schedule.every().day.at("23:59").do(send_daily_report, trader=trader, tracker=tracker,
                                         reporter=reporter, markets_scanned=markets_scanned)
    schedule.every().sunday.at("23:00").do(run_weekly_jobs, config=config, reporter=reporter)
    schedule.every(30).days.do(run_monthly_jobs, config=config)

    log.info("orchestrator.scheduler_running")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
