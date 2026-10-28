"""
Telegram bot module for handling user interactions and message management.
"""
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from core.config import AppConfig
from core.logger import LoggerMixin


class MessageTracker:
    """Tracks messages for each user to enable individual message management."""

    def __init__(self):
        self._tracker: Dict[int, List[int]] = {}

    def add_message(self, user_id: int, message_id: int):
        """Add a message to the tracker for a specific user."""
        if user_id not in self._tracker:
            self._tracker[user_id] = []
        self._tracker[user_id].append(message_id)

    def remove_message(self, user_id: int, message_id: int) -> bool:
        """
        Remove a message from the tracker for a specific user.

        Returns:
            bool: True if message was found and removed, False otherwise.
        """
        if user_id in self._tracker and message_id in self._tracker[user_id]:
            self._tracker[user_id].remove(message_id)
            return True
        return False

    def has_message(self, user_id: int, message_id: int) -> bool:
        """Check if a message exists in the tracker for a specific user."""
        return (user_id in self._tracker and
                message_id in self._tracker[user_id])


class TelegramBot(LoggerMixin):
    """Main Telegram bot class for handling user interactions."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.message_tracker = MessageTracker()

        # Initialize the bot application
        self.application = Application.builder().token(config.telegram.bot_token).build()

        # Set up handlers
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up all bot command and message handlers."""
        # Command handlers must be registered before the catch-all message
        # handler: within a group, only the first matching handler runs.
        self.application.add_handler(
            CommandHandler("start", self._handle_start_command)
        )
        self.application.add_handler(
            CommandHandler("help", self._handle_help_command)
        )
        self.application.add_handler(
            CommandHandler("status", self._handle_status_command)
        )

        # Callback query handler for button interactions
        self.application.add_handler(
            CallbackQueryHandler(self._handle_button_click)
        )

        # Message handler for all remaining incoming messages
        self.application.add_handler(
            MessageHandler(filters.ALL, self._handle_message)
        )

        self.application.add_error_handler(self._handle_error)

    def _is_editor(self, user_id: int) -> bool:
        """Check if the user is one of the configured editors."""
        return str(user_id) in self.config.telegram.user_chat_ids

    @staticmethod
    def _review_keyboard(message_id: int) -> InlineKeyboardMarkup:
        """Build the review keyboard for a news item."""
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("Confirm", callback_data=f'confirm_{message_id}'),
            InlineKeyboardButton("Delete", callback_data=f'delete_{message_id}')
        ]])

    @staticmethod
    def _parse_callback_message_id(data: str) -> Optional[int]:
        """Extract the message ID from callback data like 'delete_123'."""
        try:
            return int(data.split('_', 1)[1])
        except (IndexError, ValueError):
            return None

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle incoming messages from users or the news bot.

        Args:
            update: Telegram update object.
            context: Bot context.
        """
        # Check if update has required components
        if not update.effective_user or not update.message:
            self.logger.warning(
                "Received update without effective_user or message")
            return

        user_id = update.effective_user.id

        self.logger.info(f"Received message from user_id: {user_id}")
        self.logger.debug(
            f"Message content: {update.message.text or update.message.caption or '<No text>'}")

        # Check if the message is from the news bot
        if str(user_id) == self.config.telegram.news_bot_id:
            self.logger.info("Message identified as sent from news_bot")
            await self._handle_news_message(update, context)
        else:
            self.logger.info("Message was not from news_bot")
            await self._handle_user_message(update, context)

    async def _handle_news_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle messages from the news bot by forwarding to users with action buttons.

        The message is copied, so text, formatting and any media type
        (photo, video, document, album item, etc.) are preserved.

        Args:
            update: Telegram update object.
            context: Bot context.
        """
        if not update.message:
            self.logger.warning("Received news message update without message")
            return

        message_id = update.message.message_id
        reply_markup = self._review_keyboard(message_id)

        # Send the message to all configured users
        for chat_id in self.config.telegram.user_chat_ids:
            try:
                await context.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=update.message.chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup
                )

                # Track the message for this user
                self.message_tracker.add_message(int(chat_id), message_id)
                self.logger.info(f"Message forwarded to user {chat_id}")

            except Exception as e:
                self.logger.error(
                    f"Error forwarding message to user {chat_id}: {e}")

    async def _handle_user_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle messages from regular users.

        Args:
            update: Telegram update object.
            context: Bot context.
        """
        if not update.message:
            self.logger.warning("Received user message update without message")
            return

        # For now, just acknowledge user messages
        await update.message.reply_text(
            "Hello! I'm the news bot. I'll forward news messages to you when they arrive."
        )

    async def _handle_button_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle button clicks from inline keyboards.

        Args:
            update: Telegram update object.
            context: Bot context.
        """
        if not update.callback_query:
            self.logger.warning(
                "Received button click update without callback_query")
            return

        query = update.callback_query
        if not query.from_user:
            self.logger.warning("Received callback query without from_user")
            return

        user_id = query.from_user.id
        data = query.data or ''

        if data == 'confirmed':
            await query.answer("Already confirmed.")
            return

        if not data.startswith(('confirm_', 'delete_')):
            await query.answer()
            return

        message_id = self._parse_callback_message_id(data)

        # Check if user has permission to act on this message
        if message_id is None or not self.message_tracker.has_message(user_id, message_id):
            await query.answer(
                "❌ You don't have permission to manage this message.", show_alert=True)
            return

        if data.startswith('confirm_'):
            # Only the keyboard is edited, so this works for text and media messages alike
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Confirmed", callback_data='confirmed')
                ]])
            )
            self.message_tracker.remove_message(user_id, message_id)
            await query.answer("✅ Message confirmed.")
            self.logger.info(f"User {user_id} confirmed message {message_id}")

        else:
            await query.delete_message()
            self.message_tracker.remove_message(user_id, message_id)
            await query.answer("🗑 Message deleted.")
            self.logger.info(f"User {user_id} deleted message {message_id}")

    async def _handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not update.message:
            self.logger.warning("Received start command without message")
            return

        await update.message.reply_text(
            "🤖 Welcome to the News Bot!\n\n"
            "I'll monitor news channels and forward important news to you. "
            "You can confirm or delete messages as needed.\n\n"
            "Use /help for more information."
        )

    async def _handle_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not update.message:
            self.logger.warning("Received help command without message")
            return

        help_text = (
            "📖 <b>News Bot Help</b>\n\n"
            "<b>Commands:</b>\n"
            "• /start - Start the bot and see welcome message\n"
            "• /help - Show this help message\n"
            "• /status - Show bot status and configuration (editors only)\n\n"
            "<b>Features:</b>\n"
            "• Automatically monitors configured news channels\n"
            "• Forwards news with AI-rewritten content\n"
            "• Filters out advertisements\n"
            "• Allows you to confirm or delete messages\n\n"
            "<b>Message Actions:</b>\n"
            "• <b>Confirm</b> - Approve the news message\n"
            "• <b>Delete</b> - Remove the message from your view"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

    async def _handle_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        if not update.message or not update.effective_user:
            self.logger.warning("Received status command without message")
            return

        if not self._is_editor(update.effective_user.id):
            await update.message.reply_text("❌ This command is available to editors only.")
            return

        status_text = (
            "📊 <b>Bot Status</b>\n\n"
            "<b>Configuration:</b>\n"
            f"• Monitored channels: {len(self.config.telegram.channel_ids)}\n"
            f"• User chat IDs: {len(self.config.telegram.user_chat_ids)}\n"
            f"• News bot ID: {self.config.telegram.news_bot_id}\n\n"
            "<b>Message Tracking:</b>\n"
            f"• Total tracked messages: {sum(len(messages) for messages in self.message_tracker._tracker.values())}\n"
            f"• Active users: {len(self.message_tracker._tracker)}\n\n"
            "<b>Rate Limiting:</b>\n"
            f"• Max requests per minute: {self.config.rate_limit.max_requests_per_minute}\n"
            f"• Max tokens per minute: {self.config.rate_limit.max_tokens_per_minute}\n"
            f"• Max requests per day: {self.config.rate_limit.max_requests_per_day}"
        )
        await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

    async def _handle_error(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Log exceptions raised by handlers."""
        self.logger.error(
            f"Error while handling update: {context.error}", exc_info=context.error)

    async def start(self) -> None:
        """Start the Telegram bot."""
        self.logger.info("Starting Telegram bot...")
        await self.application.initialize()
        await self.application.start()
        if self.application.updater:
            await self.application.updater.start_polling()

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        self.logger.info("Stopping Telegram bot...")
        if self.application.updater and self.application.updater.running:
            await self.application.updater.stop()
        if self.application.running:
            await self.application.stop()
        await self.application.shutdown()
        return None
