"""
Sample test file for the news bot application.
This demonstrates the testing structure and provides examples.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import sys
from pathlib import Path

# Import modules (path setup handled by conftest.py)
from src import AppConfig, TelegramConfig, OpenAIConfig, RateLimitConfig, load_config, validate_config, setup_logger
from src import NewsParser, RateLimiter, TelegramBot, MessageTracker


class TestConfig:
    """Test configuration management."""

    def test_config_creation(self):
        """Test creating configuration objects."""
        telegram_config = TelegramConfig(
            api_id="test_id",
            api_hash="test_hash",
            bot_token="test_token",
            bot_username="test_bot",
            news_bot_id="123",
            user_chat_ids=["456", "789"],
            channel_ids=["111", "222"]
        )

        openai_config = OpenAIConfig(api_key="test_key")
        rate_limit_config = RateLimitConfig()

        app_config = AppConfig(
            telegram=telegram_config,
            openai=openai_config,
            rate_limit=rate_limit_config
        )

        assert app_config.telegram.api_id == "test_id"
        assert app_config.openai.api_key == "test_key"
        assert app_config.rate_limit.max_requests_per_minute == 3

    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        valid_config = AppConfig(
            telegram=TelegramConfig(
                api_id="test", api_hash="test", bot_token="test",
                bot_username="test", news_bot_id="123", user_chat_ids=[], channel_ids=[]
            ),
            openai=OpenAIConfig(api_key="test"),
            rate_limit=RateLimitConfig()
        )
        assert validate_config(valid_config) is True

        # Invalid config (missing api_key)
        invalid_config = AppConfig(
            telegram=TelegramConfig(
                api_id="test", api_hash="test", bot_token="test",
                bot_username="test", news_bot_id="123", user_chat_ids=[], channel_ids=[]
            ),
            openai=OpenAIConfig(api_key=""),
            rate_limit=RateLimitConfig()
        )
        assert validate_config(invalid_config) is False


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        config = RateLimitConfig()
        limiter = RateLimiter(config)

        assert limiter.token_usage == 0
        assert limiter.request_count_minute == 0
        assert limiter.request_count_day == 0

    @pytest.mark.asyncio
    async def test_rate_limiter_management(self):
        """Test rate limit management."""
        config = RateLimitConfig(
            max_requests_per_minute=2, max_tokens_per_minute=100)
        limiter = RateLimiter(config)

        # First request should pass
        result = await limiter.manage_rate_limit(50)
        assert result is True
        assert limiter.request_count_minute == 1
        assert limiter.token_usage == 50

        # Second request should pass
        result = await limiter.manage_rate_limit(30)
        assert result is True
        assert limiter.request_count_minute == 2
        assert limiter.token_usage == 80

        # Third request should be rate limited
        result = await limiter.manage_rate_limit(10)
        assert result is False


class TestMessageTracker:
    """Test message tracking functionality."""

    def test_message_tracker_initialization(self):
        """Test message tracker initialization."""
        tracker = MessageTracker()
        assert tracker._tracker == {}

    def test_add_message(self):
        """Test adding messages to tracker."""
        tracker = MessageTracker()
        tracker.add_message(123, 456)
        tracker.add_message(123, 789)
        tracker.add_message(456, 111)

        assert tracker._tracker[123] == [456, 789]
        assert tracker._tracker[456] == [111]

    def test_remove_message(self):
        """Test removing messages from tracker."""
        tracker = MessageTracker()
        tracker.add_message(123, 456)
        tracker.add_message(123, 789)

        # Remove existing message
        result = tracker.remove_message(123, 456)
        assert result is True
        assert tracker._tracker[123] == [789]

        # Try to remove non-existing message
        result = tracker.remove_message(123, 999)
        assert result is False

    def test_has_message(self):
        """Test checking if message exists in tracker."""
        tracker = MessageTracker()
        tracker.add_message(123, 456)

        assert tracker.has_message(123, 456) is True
        assert tracker.has_message(123, 789) is False
        assert tracker.has_message(456, 456) is False


class TestNewsParser:
    """Test news parser functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for testing."""
        return AppConfig(
            telegram=TelegramConfig(
                api_id="test", api_hash="test", bot_token="test",
                bot_username="test", news_bot_id="123",
                user_chat_ids=["456"], channel_ids=["789"]
            ),
            openai=OpenAIConfig(api_key="test"),
            rate_limit=RateLimitConfig()
        )

    def test_news_parser_initialization(self, mock_config):
        """Test news parser initialization."""
        with patch('news_parser.news_bot.TelegramClient'):
            parser = NewsParser(mock_config)
            assert parser.config == mock_config
            assert isinstance(parser.rate_limiter, RateLimiter)

    @pytest.mark.asyncio
    async def test_check_content_type(self, mock_config):
        """Test content type checking."""
        with patch('news_parser.news_bot.TelegramClient'), \
                patch('news_parser.news_bot.openai.chat.completions.create') as mock_openai:

            # Mock OpenAI response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "News"
            mock_openai.return_value = mock_response

            parser = NewsParser(mock_config)
            result = await parser._check_content_type("Test news content")

            assert result == "News"
            mock_openai.assert_called_once()

    @pytest.mark.asyncio
    async def test_rewrite_text(self, mock_config):
        """Test text rewriting functionality."""
        with patch('news_parser.news_bot.TelegramClient'), \
                patch('news_parser.news_bot.openai.chat.completions.create') as mock_openai:

            # Mock OpenAI response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Rewritten text"
            mock_openai.return_value = mock_response

            parser = NewsParser(mock_config)
            result = await parser._rewrite_text("Original text")

            assert result == "Rewritten text"
            mock_openai.assert_called_once()


class TestTelegramBot:
    """Test Telegram bot functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for testing."""
        return AppConfig(
            telegram=TelegramConfig(
                api_id="test", api_hash="test", bot_token="test",
                bot_username="test", news_bot_id="123",
                user_chat_ids=["456"], channel_ids=["789"]
            ),
            openai=OpenAIConfig(api_key="test"),
            rate_limit=RateLimitConfig()
        )

    def test_telegram_bot_initialization(self, mock_config):
        """Test Telegram bot initialization."""
        with patch('bot.telegram_bot.Application'):
            bot = TelegramBot(mock_config)
            assert bot.config == mock_config
            assert isinstance(bot.message_tracker, MessageTracker)


class TestIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_application_startup(self):
        """Test that the application can start up without errors."""
        # This would be a more comprehensive integration test
        # For now, we'll just test that imports work
        from src import NewsBotApplication

        app = NewsBotApplication()
        assert app.config is None
        assert app.logger is None


# Example of how to run specific tests
if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
