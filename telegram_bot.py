from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import logging

# Configure logging to save to a file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("telegram_bot_log.log"),
        logging.StreamHandler()
    ]
)

# Bot token and user list
TOKEN = '7354476983:AAG8judAhTygD-dMCZOvwcofHAZyNGdi5EY'
user_chat_ids = [490748903, 452536082]
news_bot_id = 7491816403  # news_bot account ID
message_tracker = {}  # Dictionary for tracking user messages

# Application initialization
application = Application.builder().token(TOKEN).build()


# Handling messages from news_bot
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_id = update.message.message_id

    # Logging message details for debugging
    logging.info(f"Received message from user_id: {user_id}")
    logging.info(f"Message content: {update.message.text}")

    # Check if the message is from the news_bot
    if user_id == news_bot_id:
        logging.info("Message identified as sent from news_bot.")

        # Create keyboard with buttons
        keyboard = [[
            InlineKeyboardButton("Подтвердить", callback_data='confirm'),
            InlineKeyboardButton(
                "Удалить", callback_data=f'delete_{message_id}')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send the message to the user with buttons
        for chat_id in user_chat_ids:
            # Handle photo messages
            if update.message.photo:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=update.message.photo[-1].file_id,
                    caption=update.message.caption or "<Нет текста>",
                    reply_markup=reply_markup
                )
            # Handle document messages
            elif update.message.document:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=update.message.document.file_id,
                    caption=update.message.caption or "<Нет текста>",
                    reply_markup=reply_markup
                )
            # Handle text messages or other types
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=update.message.text or "<Нет текста>",
                    reply_markup=reply_markup
                )

            # Track the message for each user
            message_tracker.setdefault(chat_id, []).append(message_id)
    else:
        logging.info("Message was not from news_bot.")


# Handling button pressing
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == 'confirm':
        await query.edit_message_text(text="Message confirmed.")
    elif query.data.startswith('delete'):
        # Deleting the message for current user only
        message_id = int(query.data.split('_')[1])
        if user_id in message_tracker and message_id in message_tracker[user_id]:
            await query.delete_message()
            message_tracker[user_id].remove(message_id)


# Register handlers
application.add_handler(MessageHandler(filters.ALL, handle_message))
application.add_handler(CallbackQueryHandler(button_handler))

# Launching the bot
if __name__ == '__main__':
    application.run_polling()
