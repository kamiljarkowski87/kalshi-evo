"""Powiadomienia Telegram — każdy zakład, dzienny raport, alerty."""
import requests
from src.core.logger import log


class TelegramReporter:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)
        self.base_url = f"https://api.telegram.org/bot{token}"

    def send(self, message: str) -> bool:
        if not self.enabled:
            log.warning("telegram.disabled")
            return False
        try:
            resp = requests.post(f"{self.base_url}/sendMessage", json={
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }, timeout=10)
            return resp.ok
        except Exception as e:
            log.error("telegram.error", error=str(e))
            return False

    def send_trade_entry(self, market: dict, debate: dict, bet: dict, side: str):
        emoji = "🟢" if side == 'yes' else "🔴"
        self.send(f"""{emoji} *NOWY ZAKŁAD [PAPER]*
📋 {market['title'][:50]}
💰 Strona: {side.upper()} @ {market['yes_bid']}¢
🎯 Moja prob: {debate['my_prob']:.0%} | Edge: {debate['edge']:+.1%}
💵 Kwota: ${bet['bet_usd']:.2f} ({bet['bet_pct']:.1f}% bankrollu)
🤖 Confidence: {debate.get('synthesis', {}).get('confidence', 'N/A')}
📊 Debata: {debate.get('synthesis', {}).get('debate_quality', 'N/A')}
⏰ Deadline: {market.get('close_time', '')[:10]}""")

    def send_daily_report(self, stats: dict):
        emoji = "📈" if stats.get('daily_pnl', 0) >= 0 else "📉"
        self.send(f"""{emoji} *RAPORT DZIENNY — Kalshi Evo*
💵 Dzienny P&L: ${stats.get('daily_pnl', 0):+.2f}
📊 Zakłady: {stats.get('bets_today', 0)} ({stats.get('wins_today', 0)}W/{stats.get('losses_today', 0)}L)
🏦 Bankroll: ${stats.get('bankroll', 0):.2f}
🔍 Przeanalizowanych rynków: {stats.get('markets_scanned', 0)}""")

    def send_weekly_reflection(self, reflection: dict):
        summary = reflection.get('week_summary', {})
        lessons = [l for l in reflection.get('lessons', []) if l.get('priority') == 'high'][:3]
        lessons_text = '\n'.join([f"• {l['lesson']}" for l in lessons]) or "Brak danych"
        self.send(f"""🧠 *TYGODNIOWA REFLEKSJA*
📊 Zakłady: {summary.get('total_bets', 0)} | Win rate: {summary.get('win_rate', 0):.0%}
💵 P&L tygodnia: ${summary.get('total_pnl', 0):+.2f}
🏆 Najlepsza kategoria: {summary.get('best_category', 'N/A')}
❌ Najgorsza: {summary.get('worst_category', 'N/A')}

*Kluczowe wnioski:*
{lessons_text}""")

    def send_alert(self, message: str):
        self.send(f"🚨 *ALERT*\n{message}")
