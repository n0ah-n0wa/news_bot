"""
Sample test file for the news bot application.
This demonstrates the testing structure and provides examples.
"""
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, MagicMock, patch

import pytest
from telegram.ext import CommandHandler, MessageHandler

# Import modules (path setup handled by conftest.py). Modules are imported
# from the same top-level packages that the patch() targets refer to.
from core.config import (
    AppConfig, TelegramConfig, OpenAIConfig, RateLimitConfig,
    load_config, validate_config, parse_list, parse_chat_identifier
)
from core.logger import setup_logger, LoggerMixin
from news_parser.news_bot import NewsParser, RateLimiter
from bot.telegram_bot import TelegramBot, MessageTracker
from main import NewsBotApplication


def make_config(**telegram_overrides) -> AppConfig:
    """Build a test configuration."""
    telegram = dict(
        api_id="test", api_hash="test", bot_token="test",
        bot_username="test", news_bot_id="123",
        user_chat_ids=["456"], channel_ids=["789"]
    )
    telegram.update(telegram_overrides)
    return AppConfig(
        telegram=TelegramConfig(**telegram),
        openai=OpenAIConfig(api_key="test"),
        rate_limit=RateLimitConfig()
    )


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

    def test_parse_list(self):
        """Comma-separated values are trimmed and empty items dropped."""
        assert parse_list(" 1, 2 ,,3 ") == ["1", "2", "3"]
        assert parse_list("") == []

    def test_parse_chat_identifier(self):
        """Numeric IDs become int (Telethon treats numeric strings as phones)."""
        assert parse_chat_identifier("-1001234567890") == -1001234567890
        assert parse_chat_identifier("@example_news") == "@example_news"

    def test_load_config_from_environment(self, monkeypatch):
        """Environment variables are parsed into typed configuration."""
        monkeypatch.setenv("TELEGRAM_CHANNEL_IDS", "-1001234567890, @example_news")
        monkeypatch.setenv("TELEGRAM_USER_CHAT_IDS", "111, 222")
        monkeypatch.delenv("TELEGRAM_SESSION_PATH", raising=False)
        monkeypatch.delenv("LOG_FILE", raising=False)

        config = load_config()

        assert config.telegram.channel_ids == [-1001234567890, "@example_news"]
        assert config.telegram.user_chat_ids == ["111", "222"]
        assert config.telegram.session_path == "sessions/news_bot_session"
        assert config.log_file == "logs/news_bot.log"


class TestLogger:
    """Test logging configuration."""

    def test_component_loggers_propagate_to_app_logger(self):
        """Component loggers are children of the configured application logger."""
        app_logger = setup_logger("news_bot", "INFO", None)
        records = []
        handler = logging.Handler()
        handler.emit = records.append
        app_logger.addHandler(handler)

        class Component(LoggerMixin):
            pass

        Component().logger.info("component message")

        assert any(r.getMessage() == "component message" for r in records)


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
    def mock_config(self, tmp_path):
        """Create a mock configuration for testing."""
        return make_config(session_path=str(tmp_path / "sessions" / "test_session"))

    def test_news_parser_initialization(self, mock_config):
        """Test news parser initialization."""
        with patch('news_parser.news_bot.TelegramClient') as mock_client:
            parser = NewsParser(mock_config)
            assert parser.config == mock_config
            assert isinstance(parser.rate_limiter, RateLimiter)
            assert parser.client is mock_client.return_value

    def test_session_stored_at_configured_path(self, mock_config, tmp_path):
        """The Telethon session uses the configured path and its directory is created."""
        with patch('news_parser.news_bot.TelegramClient') as mock_client:
            NewsParser(mock_config)
            assert mock_client.call_args.args[0] == mock_config.telegram.session_path
            assert (tmp_path / "sessions").is_dir()

    @pytest.mark.asyncio
    async def test_start_and_stop_await_client(self, mock_config):
        """start() and stop() actually await the Telethon coroutines."""
        with patch('news_parser.news_bot.TelegramClient') as mock_client:
            client = mock_client.return_value
            client.start = AsyncMock()
            client.disconnect = AsyncMock()
            client.is_connected = Mock(return_value=True)

            parser = NewsParser(mock_config)
            await parser.start()
            await parser.stop()

            client.start.assert_awaited_once()
            client.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_advert_is_not_forwarded(self, mock_config):
        """Posts classified as adverts are dropped before rewriting."""
        with patch('news_parser.news_bot.TelegramClient'):
            parser = NewsParser(mock_config)
            parser._check_content_type = AsyncMock(return_value="Advert")
            parser._rewrite_text = AsyncMock()
            parser._forward_message_to_bot = AsyncMock()

            event = Mock()
            event.message.text = "Buy now!"
            await parser._handle_new_message(event)

            parser._rewrite_text.assert_not_awaited()
            parser._forward_message_to_bot.assert_not_awaited()

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
        return make_config(bot_token="123:abc", user_chat_ids=["456", "789"])

    @staticmethod
    def make_callback_update(user_id: int, data: str):
        """Build an update with a callback query."""
        query = MagicMock()
        query.from_user.id = user_id
        query.data = data
        query.answer = AsyncMock()
        query.edit_message_reply_markup = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.delete_message = AsyncMock()
        update = MagicMock()
        update.callback_query = query
        return update, query

    def test_telegram_bot_initialization(self, mock_config):
        """Test Telegram bot initialization."""
        with patch('bot.telegram_bot.Application'):
            bot = TelegramBot(mock_config)
            assert bot.config == mock_config
            assert isinstance(bot.message_tracker, MessageTracker)

    def test_commands_registered_before_catch_all(self, mock_config):
        """Command handlers precede the catch-all handler, so commands are reachable."""
        bot = TelegramBot(mock_config)
        handlers = bot.application.handlers[0]

        command_positions = [i for i, h in enumerate(handlers) if isinstance(h, CommandHandler)]
        catch_all_position = next(
            i for i, h in enumerate(handlers) if isinstance(h, MessageHandler))

        assert len(command_positions) == 3
        assert max(command_positions) < catch_all_position

    @pytest.mark.asyncio
    async def test_news_message_copied_to_every_editor(self, mock_config):
        """Relayed messages are copied (any media type) to each editor and tracked."""
        bot = TelegramBot(mock_config)
        update = MagicMock()
        update.message.message_id = 42
        update.message.chat_id = 123
        context = MagicMock()
        context.bot.copy_message = AsyncMock()

        await bot._handle_news_message(update, context)

        assert context.bot.copy_message.await_count == 2
        for chat_id in ("456", "789"):
            context.bot.copy_message.assert_any_await(
                chat_id=chat_id, from_chat_id=123, message_id=42,
                reply_markup=bot._review_keyboard(42))
            assert bot.message_tracker.has_message(int(chat_id), 42)

    @pytest.mark.asyncio
    async def test_confirm_edits_keyboard_only(self, mock_config):
        """Confirm keeps the content (works for media cards) and clears tracking."""
        bot = TelegramBot(mock_config)
        bot.message_tracker.add_message(456, 42)
        update, query = self.make_callback_update(456, "confirm_42")

        await bot._handle_button_click(update, MagicMock())

        query.edit_message_reply_markup.assert_awaited_once()
        query.edit_message_text.assert_not_awaited()
        assert not bot.message_tracker.has_message(456, 42)

    @pytest.mark.asyncio
    async def test_delete_requires_permission(self, mock_config):
        """Delete is honoured only for messages delivered to the requesting user."""
        bot = TelegramBot(mock_config)
        bot.message_tracker.add_message(456, 42)

        update, query = self.make_callback_update(789, "delete_42")
        await bot._handle_button_click(update, MagicMock())
        query.delete_message.assert_not_awaited()

        update, query = self.make_callback_update(456, "delete_42")
        await bot._handle_button_click(update, MagicMock())
        query.delete_message.assert_awaited_once()
        assert not bot.message_tracker.has_message(456, 42)


class TestIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_application_startup(self):
        """Test that the application object can be constructed."""
        app = NewsBotApplication()
        assert app.config is None
        assert app.logger is None

    @pytest.mark.asyncio
    async def test_shutdown_request_stops_application(self):
        """Requesting shutdown makes start() return so the process can exit."""
        app = NewsBotApplication()
        app.news_parser = MagicMock()
        app.news_parser.start = AsyncMock()
        app.news_parser.stop = AsyncMock()
        async def stay_connected():
            await asyncio.sleep(3600)

        app.news_parser.run_until_disconnected = AsyncMock(side_effect=stay_connected)
        app.telegram_bot = MagicMock()
        app.telegram_bot.start = AsyncMock()
        app.telegram_bot.stop = AsyncMock()

        start_task = asyncio.create_task(app.start())
        await asyncio.sleep(0.05)
        app.request_shutdown()
        await asyncio.wait_for(start_task, timeout=1)
        await app.stop()

        app.news_parser.start.assert_awaited_once()
        app.telegram_bot.start.assert_awaited_once()
        app.news_parser.stop.assert_awaited_once()
        app.telegram_bot.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_client_disconnect_stops_application(self):
        """If the Telegram client disconnects, start() returns instead of hanging."""
        app = NewsBotApplication()
        app.news_parser = MagicMock()
        app.news_parser.start = AsyncMock()
        app.news_parser.run_until_disconnected = AsyncMock()
        app.telegram_bot = MagicMock()
        app.telegram_bot.start = AsyncMock()

        await asyncio.wait_for(app.start(), timeout=1)


# Example of how to run specific tests
if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
