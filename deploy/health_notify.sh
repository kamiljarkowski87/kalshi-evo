#!/bin/bash
# Wysyła powiadomienia Telegram dla Kalshi Evo
# Użycie: health_notify.sh crash | health_notify.sh status

TOKEN="***TELEGRAM_TOKEN_USUNIETY***"
CHAT_ID="8821116926"
DB="/home/claude-runner/kalshi-evo/memory/trade_history.db"
MODE="${1:-status}"

send_msg() {
    curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
        -d "chat_id=${CHAT_ID}" \
        -d "parse_mode=Markdown" \
        --data-urlencode "text=$1" > /dev/null
}

if [ "$MODE" = "crash" ]; then
    send_msg "🚨 *KALSHI EVO PADŁ*
Bot zatrzymał się o $(date '+%Y-%m-%d %H:%M') UTC.
Systemd automatycznie go restartuje za 30 sekund.
Sprawdź logi: \`tail -50 /home/claude-runner/kalshi-evo/logs/service.log\`"
    exit 0
fi

if [ "$MODE" = "status" ]; then
    # Sprawdź czy bot działa
    if XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user is-active kalshi.service > /dev/null 2>&1; then
        BOT_STATUS="✅ Działa"
    else
        BOT_STATUS="❌ ZATRZYMANY"
    fi

    # Statystyki z bazy
    STATS=$(python3 -c "
import sqlite3, sys
try:
    conn = sqlite3.connect('${DB}')
    c = conn.cursor()
    c.execute(\"SELECT COUNT(*), SUM(pnl_usd) FROM trades WHERE status='closed'\")
    closed, pnl = c.fetchone()
    c.execute(\"SELECT COUNT(*) FROM trades WHERE status='open'\")
    open_cnt = c.fetchone()[0]
    c.execute(\"SELECT COUNT(*) FROM debate_logs\")
    debates = c.fetchone()[0]
    pnl = pnl or 0
    print(f'zamknięte={closed} otwarte={open_cnt} pnl={pnl:.2f} debaty={debates}')
except Exception as e:
    print(f'błąd={e}')
" 2>/dev/null)

    CLOSED=$(echo $STATS | grep -oP 'zamknięte=\K[0-9]+')
    OPEN=$(echo $STATS | grep -oP 'otwarte=\K[0-9]+')
    PNL=$(echo $STATS | grep -oP 'pnl=\K[-0-9.]+')
    DEBATES=$(echo $STATS | grep -oP 'debaty=\K[0-9]+')

    send_msg "🤖 *KALSHI EVO — Poranny raport* ($(date '+%Y-%m-%d'))
Status: ${BOT_STATUS}
━━━━━━━━━━━━━━━
📊 Zakłady otwarte: ${OPEN:-?}
✅ Zakłady zamknięte: ${CLOSED:-?}
💵 Łączny P&L: \$${PNL:-?}
🧠 Zapisanych debat: ${DEBATES:-?}
━━━━━━━━━━━━━━━
Ostatnia aktualizacja: $(date '+%H:%M') UTC"
    exit 0
fi
