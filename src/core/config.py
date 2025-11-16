"""
Configuration management for the news bot application.
"""
import os
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class TelegramConfig:
    """Telegram API configuration."""
    api_id: str
    api_hash: str
    bot_token: str
    bot_username: str
    news_bot_id: str
    user_chat_ids: List[str]
    channel_ids: List[str]


@dataclass
class OpenAIConfig:
    """OpenAI API configuration."""
    api_key: str
    model: str = "gpt-3.5-turbo"
    max_tokens: int = 500
    temperature: float = 0.0


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    max_tokens_per_minute: int = 40000
    max_requests_per_minute: int = 3
    max_requests_per_day: int = 200


@dataclass
class AppConfig:
    """Main application configuration."""
    telegram: TelegramConfig
    openai: OpenAIConfig
    rate_limit: RateLimitConfig
    log_level: str = "INFO"
    log_file: str = "news_bot.log"


def load_config() -> AppConfig:
    """
    Load configuration from environment variables.

    Returns:
        AppConfig: Loaded configuration object.
    """
    # Telegram configuration
    telegram_config = TelegramConfig(
        api_id=os.getenv("TELEGRAM_API_ID", ""),
        api_hash=os.getenv("TELEGRAM_API_HASH", ""),
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        bot_username=os.getenv("TELEGRAM_BOT_USERNAME", ""),
        news_bot_id=os.getenv("TELEGRAM_NEWS_BOT_ID", ""),
        user_chat_ids=os.getenv("TELEGRAM_USER_CHAT_IDS", "").split(
            ",") if os.getenv("TELEGRAM_USER_CHAT_IDS") else [],
        channel_ids=os.getenv("TELEGRAM_CHANNEL_IDS", "").split(
            ",") if os.getenv("TELEGRAM_CHANNEL_IDS") else []
    )

    # OpenAI configuration
    openai_config = OpenAIConfig(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "500")),
        temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.0"))
    )

    # Rate limiting configuration
    rate_limit_config = RateLimitConfig(
        max_tokens_per_minute=int(os.getenv("MAX_TOKENS_PER_MINUTE", "40000")),
        max_requests_per_minute=int(os.getenv("MAX_REQUESTS_PER_MINUTE", "3")),
        max_requests_per_day=int(os.getenv("MAX_REQUESTS_PER_DAY", "200"))
    )

    # Main application configuration
    config = AppConfig(
        telegram=telegram_config,
        openai=openai_config,
        rate_limit=rate_limit_config,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=os.getenv("LOG_FILE", "news_bot.log")
    )

    return config


def validate_config(config: AppConfig) -> bool:
    """
    Validate that all required configuration values are present.

    Args:
        config: Configuration object to validate.

    Returns:
        bool: True if configuration is valid, False otherwise.
    """
    required_fields = [
        config.telegram.api_id,
        config.telegram.api_hash,
        config.telegram.bot_token,
        config.telegram.bot_username,
        config.telegram.news_bot_id,
        config.openai.api_key
    ]

    return all(field for field in required_fields)




