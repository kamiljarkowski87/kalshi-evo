"""Główne limity i kill switch. Każda zmiana wymaga osobnego zatwierdzenia."""
from src.core.logger import log


class RiskManager:
    def __init__(self, config):
        self.max_daily_loss_pct = config.max_daily_loss_pct
        self.max_position_pct = config.max_position_pct
        self.starting_bankroll = config.starting_bankroll
        self._risk_multiplier = 1.0
        self._daily_pnl = 0.0
        self._halted = False

    def apply_risk_multiplier(self, multiplier: float) -> None:
        self._risk_multiplier = multiplier
        log.warning("risk.multiplier_applied", multiplier=multiplier)

    def record_pnl(self, pnl: float) -> None:
        self._daily_pnl += pnl
        loss_pct = abs(self._daily_pnl) / self.starting_bankroll
        if self._daily_pnl < 0 and loss_pct >= self.max_daily_loss_pct:
            self._halted = True
            log.error("risk.daily_halt", daily_pnl=self._daily_pnl, loss_pct=loss_pct)

    def is_halted(self) -> bool:
        return self._halted

    def reset_daily(self) -> None:
        self._daily_pnl = 0.0
        self._halted = False

    def get_portfolio_state(self, bankroll: float) -> dict:
        return {
            "bankroll": bankroll,
            "daily_pnl": self._daily_pnl,
            "daily_loss_limit": -self.starting_bankroll * self.max_daily_loss_pct,
            "halted": self._halted,
            "risk_multiplier": self._risk_multiplier,
        }
