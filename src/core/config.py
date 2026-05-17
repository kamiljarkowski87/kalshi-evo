"""Konfiguracja systemu — wszystko z .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Kalshi
    kalshi_api_key_id: str = ""
    kalshi_private_key_path: str = "./secrets/kalshi_private_key.pem"
    kalshi_env: str = "demo"

    # Polymarket
    polymarket_api_key: str = ""
    polymarket_wallet_address: str = ""

    # AI
    anthropic_api_key: str = ""

    # Dane zewnętrzne
    noaa_api_key: str = ""
    fred_api_key: str = ""
    espn_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    news_api_key: str = ""

    # Monitoring
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # System
    trading_mode: str = "paper"
    starting_bankroll: float = Field(default=1000.0)
    max_daily_loss_pct: float = Field(default=0.05)
    max_position_pct: float = Field(default=0.03)
    log_level: str = "INFO"

    # Ścieżki
    db_path: str = "./memory/trade_history.db"
    calibration_path: str = "./memory/calibration_data.jsonl"
    reflections_path: str = "./memory/weekly_reflections.jsonl"
    source_weights_path: str = "./memory/source_weights.json"

    def is_paper(self) -> bool:
        return self.trading_mode == "paper"

    def has_kalshi_keys(self) -> bool:
        return bool(self.kalshi_api_key_id and Path(self.kalshi_private_key_path).exists())
