"""
Telegram bot module for handling user interactions and message management.
"""
from typing import Dict, List, Set
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from core.config import AppConfig, TelegramConfig
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
        # Message handler for all incoming messages
        self.application.add_handler(
            MessageHandler(filters.ALL, self._handle_message)
        )

        # Callback query handler for button interactions
        self.application.add_handler(
            CallbackQueryHandler(self._handle_button_click)
        )

        # Command handlers
        self.application.add_handler(
            CommandHandler("start", self._handle_start_command)
        )
        self.application.add_handler(
            CommandHandler("help", self._handle_help_command)
        )
        self.application.add_handler(
            CommandHandler("status", self._handle_status_command)
        )

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
        message_id = update.message.message_id

        self.logger.info(f"Received message from user_id: {user_id}")
        self.logger.info(
            f"Message content: {update.message.text or '<No text>'}...")

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

        Args:
            update: Telegram update object.
            context: Bot context.
        """
        if not update.message:
            self.logger.warning("Received news message update without message")
            return

        # Create keyboard with action buttons
        keyboard = [[
            InlineKeyboardButton("Confirm", callback_data='confirm'),
            InlineKeyboardButton(
                "Delete", callback_data=f'delete_{update.message.message_id}')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send the message to all configured users
        for chat_id in self.config.telegram.user_chat_ids:
            try:
                # Handle different message types
                if update.message.photo:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=update.message.photo[-1].file_id,
                        caption=update.message.caption or "<No text>",
                        reply_markup=reply_markup
                    )
                elif update.message.document:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=update.message.document.file_id,
                        caption=update.message.caption or "<No text>",
                        reply_markup=reply_markup
                    )
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=update.message.text or "<No text>",
                        reply_markup=reply_markup
                    )

                # Track the message for this user
                self.message_tracker.add_message(
                    int(chat_id), update.message.message_id)
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
        await query.answer()

        if query.data == 'confirm':
            await query.edit_message_text(text="✅ Message confirmed.")
            self.logger.info(f"User {user_id} confirmed a message")

        elif query.data and query.data.startswith('delete'):
            # Extract message ID from callback data
            message_id = int(query.data.split('_')[1])

            # Check if user has permission to delete this message
            if self.message_tracker.has_message(user_id, message_id):
                await query.delete_message()
                self.message_tracker.remove_message(user_id, message_id)
                self.logger.info(
                    f"User {user_id} deleted message {message_id}")
            else:
                await query.edit_message_text(text="❌ You don't have permission to delete this message.")

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

        help_text = """
        📖 **News Bot Help**
        
        **Commands:**
        • /start - Start the bot and see welcome message
        • /help - Show this help message
        • /status - Show bot status and configuration
        
        **Features:**
        • Automatically monitors configured news channels
        • Forwards news with AI-rewritten content
        • Allows you to confirm or delete messages
        • Filters out advertisements and personal opinions
        
        **Message Actions:**
        • **Confirm** - Approve the news message
        • **Delete** - Remove the message from your view
        
        The bot will only forward messages that are identified as news content.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def _handle_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        if not update.message:
            self.logger.warning("Received status command without message")
            return

        status_text = f"""
        📊 **Bot Status**
        
        **Configuration:**
        • Monitored channels: {len(self.config.telegram.channel_ids)}
        • User chat IDs: {len(self.config.telegram.user_chat_ids)}
        • News bot ID: {self.config.telegram.news_bot_id}
        
        **Message Tracking:**
        • Total tracked messages: {sum(len(messages) for messages in self.message_tracker._tracker.values())}
        • Active users: {len(self.message_tracker._tracker)}
        
        **Rate Limiting:**
        • Max requests per minute: {self.config.rate_limit.max_requests_per_minute}
        • Max tokens per minute: {self.config.rate_limit.max_tokens_per_minute}
        • Max requests per day: {self.config.rate_limit.max_requests_per_day}
        """
        await update.message.reply_text(status_text, parse_mode='Markdown')

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
        if self.application.updater:
            await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        return None
