# import db
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import logging
from io import BytesIO

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
news_bot_id = 7491816403    # news_bot account ID

# Application initialization
application = Application.builder().token(TOKEN).build()

# Create keyboard with buttons
keyboard = [[
    InlineKeyboardButton("Подтвердить", callback_data='confirm'),
    InlineKeyboardButton(
        "Удалить", callback_data='delete')
]]
reply_markup = InlineKeyboardMarkup(keyboard)


# Handling messages from news_bot
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Logging message details for debugging
    logging.info(f"Received message from user_id: {user_id}")
    logging.info(f"Message content: {update.message.text or '<Нет текста>'}")

    # Check if the message is from the news_bot
    if user_id == news_bot_id:
        logging.info("Message identified as sent from news_bot.")

        # Check that the message is not a reply
        if not update.message.reply_to_message:
            # Send the message to the user with buttons
            for chat_id in user_chat_ids:
                sent_message = None
                # Handle photo messages
                if update.message.photo:
                    sent_message = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=update.message.photo[-1].file_id,
                        caption=update.message.caption or "<Нет текста>",
                        reply_markup=reply_markup
                    )
                # Handle video messages
                elif update.message.video:
                    sent_message = await context.bot.send_video(
                        chat_id=chat_id,
                        video=update.message.video.file_id,
                        caption=update.message.caption or "<Нет текста>",
                        reply_markup=reply_markup
                    )
                # Handle document messages
                elif update.message.document:
                    sent_message = await context.bot.send_document(
                        chat_id=chat_id,
                        document=update.message.document.file_id,
                        caption=update.message.caption or "<Нет текста>",
                        reply_markup=reply_markup
                    )
                # Handle text messages or other types
                else:
                    sent_message = await context.bot.send_message(
                        chat_id=chat_id,
                        text=update.message.text or "<Нет текста>",
                        reply_markup=reply_markup
                    )

                # Track the message for each user
                if sent_message:
                    logging.info(f"Message sent to chat_id: {chat_id}, message_id: {sent_message.message_id}")
                else:
                    logging.warning(
                        f"Failed to send message to chat_id: {chat_id}")
        else:
            logging.info("Message is a reply, ignoring in handle_message.")
    else:
        logging.info("Message was not from news_bot.")


# Handling user replies (editing)
async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_to_message = update.message.reply_to_message

    user_id = update.effective_user.id

    # Checking reply type from user (photo, video, etc.)
    if update.message.photo:
        input_media = InputMediaPhoto(
            media=update.message.photo[-1].file_id,
            caption=reply_to_message.caption or update.message.caption or "<Нет текста>"
        )
        await reply_to_message.edit_media(
            media=input_media,
            reply_markup=reply_markup
        )
    elif update.message.video:
        input_media = InputMediaVideo(
            media=update.message.video.file_id,
            caption=reply_to_message.caption or update.message.caption or "<Нет текста>"
        )
        await reply_to_message.edit_media(
            media=input_media,
            reply_markup=reply_markup
        )
    elif update.message.text:
        # If the original message had a caption (photo or video), we edit the caption
        if reply_to_message.photo or reply_to_message.video:
            await reply_to_message.edit_caption(
                caption=update.message.text,
                reply_markup=reply_markup
            )
        else:
            # If it's a plain text message
            await reply_to_message.edit_text(
                text=update.message.text,
                reply_markup=reply_markup
            )
    else:
        logging.warning(
            "No valid content in the user's reply to edit the message.")

    # Deleting reply from user
    await update.message.delete()
    logging.info(f"Reply from user {user_id} processed and message updated.")


# Handling button pressing
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == 'confirm':
        return
        raw = query.message.photo[-1].file_id
        file_info = await context.bot.get_file(raw)
        f = BytesIO(await file_info.download_as_bytearray())
        db.addpost(" ", query.message.text or query.message.caption, f.read())
        await query.edit_message_reply_markup()
    elif query.data.startswith('delete'):
        message_id = query.message.message_id
        await query.delete_message()


# Register handlers with more specific filters
application.add_handler(MessageHandler(
    filters.REPLY & filters.User(user_chat_ids), handle_reply))
application.add_handler(MessageHandler(filters.User(
    news_bot_id) & ~filters.REPLY, handle_message))
application.add_handler(CallbackQueryHandler(button_handler))

# loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
logging.getLogger("httpx").setLevel(logging.WARNING)  # оффаем ненужные логи

# Launching the bot
if __name__ == '__main__':
    application.run_polling()
