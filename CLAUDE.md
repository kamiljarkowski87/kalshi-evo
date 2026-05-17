# CLAUDE.md — Kalshi Evo

## Projekt
Autonomiczny system wieloagentowy do obstawiania na Kalshi prediction markets.
Hosting: mariusz128.mikrus.xyz | User: claude-runner

## Zasady pracy

1. **PLAN FIRST, CODE LATER:**
   - Przed każdą zmianą: analiza plików → pełny plan → czekaj na "tak" → koduj
   - Plan zawiera: cel, pliki do zmiany, kroki, ryzyka, rollback strategy
   - Zadania dotyczące >3 plików lub architektury: dziel na fazy

2. **AUTONOMIA:**
   Po zatwierdzeniu planu — pracuj autonomicznie aż do końca fazy.

3. **BEZPIECZEŃSTWO:**
   - Nigdy nie hardcode kluczy API — wyłącznie zmienne środowiskowe z .env
   - Zawsze paper trading domyślnie — live wymaga ręcznej zmiany TRADING_MODE=live
   - Każda zmiana w risk_manager.py wymaga osobnego "tak" od użytkownika
   - Klucze RSA tylko w katalogu secrets/ (w .gitignore)

## Struktura
- `src/core/` — Kalshi client, config, logger
- `src/data/` — źródła danych zewnętrznych
- `src/agents/` — specjaliści, debata, decyzja, ryzyko, uczenie
- `src/execution/` — paper trader, live trader
- `src/monitoring/` — Telegram, dashboard
- `memory/` — SQLite, historia zakładów, kalibracja
- `logs/` — logi decyzji i debat
- `secrets/` — klucze RSA (NIGDY w git)

## Stack
- Python 3.12, SQLite, LangGraph (opcjonalnie)
- LLM: claude-sonnet-4-6
- Auth: RSA-PSS (Kalshi wymaga podpisanych requestów)

## Git
- Commity po polsku, opisowe
- Branch main, push po każdej fazie
