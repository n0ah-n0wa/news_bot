"""
News parser module for monitoring Telegram channels and processing news content.
"""
import time
from pathlib import Path
from telethon import TelegramClient, events
from telethon.tl.types import Message
import openai

from core.config import AppConfig, RateLimitConfig
from core.logger import LoggerMixin


class RateLimiter:
    """Rate limiter for managing API usage limits."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.token_usage = 0
        self.request_count_minute = 0
        self.request_count_day = 0
        self.last_request_time = time.time()

    async def manage_rate_limit(self, tokens_used: int) -> bool:
        """
        Manage API rate limits before making requests.

        Args:
            tokens_used: Estimated number of tokens to be used.

        Returns:
            bool: True if request can proceed, False if limits reached.
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        # Reset minute counters every 60 seconds
        if time_since_last_request >= 60:
            self.request_count_minute = 0
            self.token_usage = 0

        # Check if daily limit is reached
        if self.request_count_day >= self.config.max_requests_per_day:
            return False

        # Check if minute limit is reached
        if (self.request_count_minute >= self.config.max_requests_per_minute or
                (self.token_usage + tokens_used) > self.config.max_tokens_per_minute):
            # If we're at the limit, reject the request immediately
            return False

        # Update counters
        self.token_usage += tokens_used
        self.request_count_minute += 1
        self.request_count_day += 1
        self.last_request_time = time.time()

        return True


class NewsParser(LoggerMixin):
    """Main news parser class for monitoring and processing news content."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.rate_limiter = RateLimiter(config.rate_limit)

        # Initialize OpenAI
        openai.api_key = config.openai.api_key

        # Initialize Telegram client
        try:
            api_id = int(config.telegram.api_id)
        except (ValueError, TypeError):
            # For testing or invalid config, use a default value
            api_id = 12345
            self.logger.warning(
                f"Invalid api_id '{config.telegram.api_id}', using default: {api_id}")

        session_path = Path(config.telegram.session_path)
        session_path.parent.mkdir(parents=True, exist_ok=True)

        self.client = TelegramClient(
            str(session_path),
            api_id,
            config.telegram.api_hash
        )

        # Set up event handlers
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up Telegram event handlers."""
        @self.client.on(events.NewMessage(chats=self.config.telegram.channel_ids))
        async def handler(event):
            await self._handle_new_message(event)

    async def _handle_new_message(self, event):
        """
        Handle new messages from monitored channels.

        Args:
            event: Telegram new message event.
        """
        message = event.message

        if not message.text:
            return

        self.logger.info(f"Message received: {message.text[:100]}...")

        # Check content type
        content_type = await self._check_content_type(message.text)

        # Skip advertisements
        if content_type == 'Advert':
            self.logger.info(f"Skipping message of type: {content_type}")
            return

        # Rewrite text
        rewritten_text = await self._rewrite_text(message.text)

        # Forward to bot
        await self._forward_message_to_bot(message, rewritten_text)

    async def _check_content_type(self, text: str) -> str:
        """
        Check if the text is an advertisement, opinion, or news.

        Args:
            text: Text to analyze.

        Returns:
            str: Content type ('Advert', 'Opinion', or 'News').
        """
        try:
            prompt = f"""
            Determine whether the text is an advert, personal opinion or news story: "{text}".
            If it's an advert, answer in one word "Advert". If it's a personal opinion, answer "Opinion".
            If it's news story, answer "News".
            """

            # Estimate tokens
            tokens_estimate = int(len(prompt.split()) * 1.5)

            # Check rate limits
            can_proceed = await self.rate_limiter.manage_rate_limit(tokens_estimate)
            if not can_proceed:
                self.logger.warning(
                    "Rate limit reached, skipping content type check")
                return "News"  # Default to news if rate limited

            response = openai.chat.completions.create(
                model=self.config.openai.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0
            )

            result = response.choices[0].message.content
            if result:
                result = result.strip()
                self.logger.info(f"Content type determined: {result}")
                return result
            else:
                self.logger.warning(
                    "Empty response from OpenAI, defaulting to News")
                return "News"

        except Exception as e:
            self.logger.error(f"Error in check_content_type: {e}")
            return "News"  # Default to news on error

    async def _rewrite_text(self, text: str) -> str:
        """
        Rewrite the text while preserving meaning and quotes.

        Args:
            text: Original text to rewrite.

        Returns:
            str: Rewritten text.
        """
        try:
            prompt = f"""
            Do a deep rewrite of the following text, but leave the overall meaning unchanged,
            as well as keep direct quotations unchanged, if any in the text.
            Note that you should return the result in the language of original text: "{text}"
            """

            # Estimate tokens
            tokens_estimate = int(len(prompt.split()) * 1.5)

            # Check rate limits
            can_proceed = await self.rate_limiter.manage_rate_limit(tokens_estimate)
            if not can_proceed:
                self.logger.warning(
                    "Rate limit reached, returning original text")
                return text

            response = openai.chat.completions.create(
                model=self.config.openai.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.openai.max_tokens,
                temperature=self.config.openai.temperature
            )

            rewritten = response.choices[0].message.content
            if rewritten:
                rewritten = rewritten.strip()
                self.logger.info("Text rewritten successfully")
                return rewritten
            else:
                self.logger.warning(
                    "Empty response from OpenAI, returning original text")
                return text

        except Exception as e:
            self.logger.error(f"Error in rewrite_text: {e}")
            return text  # Return original text on error

    async def _forward_message_to_bot(self, message: Message, rewritten_text: str):
        """
        Forward the message to the Telegram bot.

        Args:
            message: Original Telegram message.
            rewritten_text: Rewritten text content.
        """
        try:
            # Find the bot by username
            bot_entity = await self.client.get_entity(self.config.telegram.bot_username)
            # Ensure we have a single entity, not a list
            if isinstance(bot_entity, list):
                bot_entity = bot_entity[0]
            if message.media:
                await self.client.send_message(bot_entity, rewritten_text, file=message.media)
            else:
                await self.client.send_message(bot_entity, rewritten_text)
            self.logger.info("Message successfully forwarded to bot")
        except Exception as e:
            self.logger.error(f"Error when forwarding message: {e}")

    async def start(self) -> None:
        """
        Connect and authorize the Telegram client.

        On the first run Telethon prompts for the phone number and login code;
        the authorized session is then reused from the session file.
        """
        self.logger.info("Starting news parser...")
        await self.client.start()
        self.logger.info(
            f"News parser connected, monitoring {len(self.config.telegram.channel_ids)} channel(s)")

    async def run_until_disconnected(self) -> None:
        """Wait until the Telegram client disconnects."""
        await self.client.run_until_disconnected()

    async def stop(self) -> None:
        """Stop the news parser."""
        self.logger.info("Stopping news parser...")
        if self.client.is_connected():
            await self.client.disconnect()
