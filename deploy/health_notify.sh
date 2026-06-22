#!/bin/bash
# Wysyła powiadomienia Telegram dla Kalshi Evo
# Użycie: health_notify.sh crash | health_notify.sh status

TOKEN="***TELEGRAM_TOKEN_USUNIETY***"
CHAT_ID="8821116926"
DB="/home/claude-runner/kalshi-evo/memory/trade_history.db"
LOG="/home/claude-runner/kalshi-evo/logs/service.log"
MODE="${1:-status}"

send_msg() {
    curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
        -d "chat_id=${CHAT_ID}" \
        -d "parse_mode=Markdown" \
        --data-urlencode "text=$1" > /dev/null
}

if [ "$MODE" = "crash" ]; then
    LAST_LOG=$(tail -3 "$LOG" 2>/dev/null | tr '\n' ' ')
    send_msg "🚨 *KALSHI EVO PADŁ*
Czas: $(date '+%Y-%m-%d %H:%M') UTC
Systemd restartuje go za 30 sekund.
Ostatnie logi: ${LAST_LOG:0:200}"
    exit 0
fi

if [ "$MODE" = "status" ]; then
    # Status bota
    if XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user is-active kalshi.service > /dev/null 2>&1; then
        BOT_STATUS="✅ Działa"
    else
        BOT_STATUS="❌ ZATRZYMANY"
    fi

    # Statystyki z bazy danych
    STATS=$(python3 -c "
import sqlite3
from datetime import datetime, timedelta

try:
    conn = sqlite3.connect('${DB}')
    c = conn.cursor()

    # Ogólne
    c.execute(\"SELECT COUNT(*), SUM(pnl_usd) FROM trades WHERE status='closed'\")
    closed, total_pnl = c.fetchone()
    total_pnl = total_pnl or 0

    c.execute(\"SELECT COUNT(*) FROM trades WHERE status='open'\")
    open_cnt = c.fetchone()[0]

    # Dzisiaj
    today = datetime.utcnow().strftime('%Y-%m-%d')
    c.execute(\"SELECT COUNT(*) FROM trades WHERE DATE(created_at)=?\", (today,))
    trades_today = c.fetchone()[0]

    c.execute(\"SELECT COUNT(*) FROM debate_logs WHERE DATE(created_at)=?\", (today,))
    debates_today = c.fetchone()[0]

    # Łączne debaty
    c.execute('SELECT COUNT(*) FROM debate_logs')
    debates_total = c.fetchone()[0]

    # Wygrane/przegrane
    c.execute(\"SELECT COUNT(*) FROM trades WHERE outcome='WIN'\")
    wins = c.fetchone()[0]
    c.execute(\"SELECT COUNT(*) FROM trades WHERE outcome='LOSS'\")
    losses = c.fetchone()[0]

    # Ostatni zakład
    c.execute(\"SELECT ticker, side, created_at FROM trades ORDER BY created_at DESC LIMIT 1\")
    last = c.fetchone()
    last_trade = f'{last[0][:20]} {last[1].upper()} ({last[2][:10]})' if last else 'brak'

    # Błędy z ostatniej godziny (z logu)
    print(f'closed={closed} pnl={total_pnl:.2f} open={open_cnt} wins={wins} losses={losses} trades_today={trades_today} debates_today={debates_today} debates_total={debates_total} last={last_trade}')
except Exception as e:
    print(f'error={e}')
" 2>/dev/null)

    CLOSED=$(echo "$STATS" | grep -oP 'closed=\K[0-9]+')
    PNL=$(echo "$STATS" | grep -oP 'pnl=\K[-0-9.]+')
    OPEN=$(echo "$STATS" | grep -oP 'open=\K[0-9]+')
    WINS=$(echo "$STATS" | grep -oP 'wins=\K[0-9]+')
    LOSSES=$(echo "$STATS" | grep -oP 'losses=\K[0-9]+')
    TRADES_TODAY=$(echo "$STATS" | grep -oP 'trades_today=\K[0-9]+')
    DEBATES_TODAY=$(echo "$STATS" | grep -oP 'debates_today=\K[0-9]+')
    DEBATES_TOTAL=$(echo "$STATS" | grep -oP 'debates_total=\K[0-9]+')
    LAST=$(echo "$STATS" | grep -oP 'last=\K.+')

    # Błędy z logów (ostatnie 24h)
    ERRORS=$(grep -c '"level": "error"' "$LOG" 2>/dev/null || echo 0)
    WARNINGS=$(grep -c '"level": "warning"' "$LOG" 2>/dev/null || echo 0)

    # Ocena uczenia się
    if [ "${DEBATES_TODAY:-0}" -gt 0 ]; then
        LEARNING="✅ Uczy się (${DEBATES_TODAY} debat dziś)"
    elif [ "${DEBATES_TOTAL:-0}" -gt 0 ]; then
        LEARNING="🟡 Brak nowych debat dziś"
    else
        LEARNING="❌ Brak danych o uczeniu"
    fi

    send_msg "🤖 *KALSHI EVO — Raport dzienny*
📅 $(date '+%Y-%m-%d %H:%M') UTC

*Status:* ${BOT_STATUS}
*Uczenie:* ${LEARNING}
━━━━━━━━━━━━━━━
📈 *Aktywność dziś:*
  Nowe zakłady: ${TRADES_TODAY:-0}
  Debaty zapisane: ${DEBATES_TODAY:-0}

💰 *Wyniki łączne:*
  Otwarte pozycje: ${OPEN:-?}
  Zamknięte: ${CLOSED:-?} (${WINS:-0}W / ${LOSSES:-0}L)
  Łączny P&L: \$${PNL:-0}

⚠️ *Logi (cały czas):*
  Błędy: ${ERRORS} | Ostrzeżenia: ${WARNINGS}

📌 *Ostatni zakład:*
  ${LAST:-brak}
━━━━━━━━━━━━━━━
Bankroll start: \$1000 → teraz: \$$(python3 -c "print(round(1000 + ${PNL:-0} - 0, 2))" 2>/dev/null || echo '?')"
    exit 0
fi
