# Kalshi Evo — Autonomiczny System Prediction Markets

Wieloagentowy system AI do analizy i obstawiania na Kalshi prediction markets.

## Co robi
- Co 5 minut skanuje prawdziwe rynki Kalshi
- Uruchamia **3-rundową debatę** między agentami specjalistami (ekonomia, krypto, sport, pogoda, polityka)
- Każdy agent przed oceną pobiera **aktualne dane z internetu** (Perplexity AI)
- Syntezer agreguje wyniki i oblicza edge względem ceny rynkowej
- **Sanity checker** odrzuca zakłady bez wystarczającego edge lub niskiej jakości
- **Kelly criterion** oblicza optymalną wielkość zakładu
- Cotygodniowa refleksja — system uczy się na własnych błędach

## Stack
- Python 3.12
- LLM: Claude Sonnet (claude-sonnet-4-6) — Anthropic API
- Wyszukiwanie: Perplexity AI (sonar) — aktualne dane
- Baza danych: SQLite
- Auth Kalshi: RSA-PSS

## Uruchomienie
```bash
screen -r kalshi        # podgląd działającego systemu
tail -f logs/orchestrator.log   # logi na żywo
```

## Konfiguracja (.env)
```
ANTHROPIC_API_KEY=...
PERPLEXITY_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
KALSHI_API_KEY_ID=...
KALSHI_PRIVATE_KEY_PATH=./secrets/kalshi_private_key.pem
KALSHI_ENV=prod
TRADING_MODE=paper   # zmień na live dla prawdziwych zakładów
STARTING_BANKROLL=1000
```

## Tryby
- `TRADING_MODE=paper` — symulacja (domyślnie, bezpieczne)
- `TRADING_MODE=live` — prawdziwe zakłady (wymaga środków na Kalshi)

## Struktura projektu
```
src/
  core/           — klient Kalshi, config, logger, baza danych
  agents/
    debate/       — 3-rundowa debata agentów
    decision/     — sanity checker
    risk/         — Kelly sizer, risk manager
    learning/     — tygodniowa refleksja, kalibracja
  data/           — Perplexity search, źródła danych
  execution/      — paper trader
  monitoring/     — Telegram bot, performance tracker
memory/           — SQLite historia zakładów
logs/             — logi decyzji
secrets/          — klucze RSA (nie w git)
```

## Hosting
Serwer Mikrus | IP: 135.181.138.156 | User: claude-runner
