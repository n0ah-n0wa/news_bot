# import db
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import logging
from io import BytesIO
import asyncio
import time
import openai

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
openai_api_key = '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'
user_chat_ids = [490748903, 452536082]
news_bot_id = 7491816403    # news_bot account ID

# Application initialization
application = Application.builder().token(TOKEN).build()

# Initialize OpenAI API
openai.api_key = openai_api_key

# API rate limits
MAX_TOKENS_PER_MINUTE = 40000
MAX_REQUESTS_PER_MINUTE = 3
MAX_REQUESTS_PER_DAY = 200

# Current usage tracking
token_usage = 0
request_count_minute = 0
request_count_day = 0
last_request_time = time.time()

# Keyboard for news posts
keyboard = [[
    InlineKeyboardButton("Подтвердить", callback_data='confirm'),
    InlineKeyboardButton("Удалить", callback_data='delete'),
    InlineKeyboardButton("Расширить", callback_data='expand')
]]
reply_markup = InlineKeyboardMarkup(keyboard)

# Keyboard for article response
article_keyboard = [[
    InlineKeyboardButton("Подтвердить", callback_data='confirm_article'),
    InlineKeyboardButton("Удалить", callback_data='delete_article')
]]
article_reply_markup = InlineKeyboardMarkup(article_keyboard)

# Keyboard for on-demand article generation
generate_article_keyboard = [[
    InlineKeyboardButton("Сгенерировать", callback_data='generate_article')
]]
generate_article_reply_markup = InlineKeyboardMarkup(generate_article_keyboard)


# Managing API limits
async def manage_rate_limit(tokens_used):
    global request_count_minute, request_count_day, last_request_time, token_usage

    current_time = time.time()
    time_since_last_request = current_time - last_request_time

    # Reset minute counters every 60 seconds
    if time_since_last_request >= 60:
        request_count_minute = 0
        token_usage = 0

    # Check if daily limit is reached
    if request_count_day >= MAX_REQUESTS_PER_DAY:
        logging.error("Daily request limit reached. Stopping execution.")
        return False

    # Check if minute limit is reached
    if request_count_minute >= MAX_REQUESTS_PER_MINUTE or (token_usage + tokens_used) > MAX_TOKENS_PER_MINUTE:
        wait_time = 60 - time_since_last_request
        logging.info(
            f"Rate limit reached, waiting for {wait_time:.2f} seconds...")
        await asyncio.sleep(wait_time)
        request_count_minute = 0
        token_usage = 0

    # Update counters
    token_usage += tokens_used
    request_count_minute += 1
    request_count_day += 1
    last_request_time = time.time()

    return True


# Handling messages from news_bot
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(
        f"Received message from news_bot with content: {update.message.text_html or ' '}")

    text = update.message.text_html or update.message.caption_html or " "

    for chat_id in user_chat_ids:
        sent_message = None

        # Handle photo messages
        if update.message.photo:
            sent_message = await context.bot.send_photo(
                chat_id=chat_id,
                photo=update.message.photo[-1].file_id,
                caption=text,
                reply_markup=reply_markup, parse_mode="html"
            )
        # Handle video messages
        elif update.message.video:
            sent_message = await context.bot.send_video(
                chat_id=chat_id,
                video=update.message.video.file_id,
                caption=text,
                reply_markup=reply_markup, parse_mode="html"
            )
        # Handle document messages
        elif update.message.document:
            sent_message = await context.bot.send_document(
                chat_id=chat_id,
                document=update.message.document.file_id,
                caption=text,
                reply_markup=reply_markup, parse_mode="html"
            )
        # Handle text messages or other types
        else:
            sent_message = await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup, parse_mode="html"
            )

        # Track the message for each user
        if sent_message:
            logging.info(
                f"Message sent to chat_id: {chat_id}, message_id: {sent_message.message_id}")
        else:
            logging.warning(
                f"Failed to send message to chat_id: {chat_id}")


# Handling user replies (editing)
async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_to_message = update.message.reply_to_message
    user_id = update.effective_user.id

    input_media = None

    # Determining media type (photo, video, etc.) for editing
    if update.message.photo:
        input_media = InputMediaPhoto(
            media=update.message.photo[-1].file_id,
            caption=update.message.caption_html or reply_to_message.caption_html or " ", parse_mode="html"
        )
    elif update.message.video:
        input_media = InputMediaVideo(
            media=update.message.video.file_id,
            caption=update.message.caption_html or reply_to_message.caption_html or " ", parse_mode="html"
        )

    # Editing media or/and text
    if input_media:
        await reply_to_message.edit_media(
            media=input_media,
            reply_markup=reply_markup
        )
    elif update.message.text_html:
        # If original message has media - editing caption
        if reply_to_message.photo or reply_to_message.video:
            await reply_to_message.edit_caption(
                caption=update.message.text_html,
                reply_markup=reply_markup, parse_mode="html"
            )
        # If it was plain text - editing text
        else:
            await reply_to_message.edit_text(
                text=update.message.text_html,
                reply_markup=reply_markup, parse_mode="html"
            )

    # Deleting user's reply message
    await update.message.delete()
    logging.info(f"Reply from user {user_id} processed and message updated.")


# Processing non-reply messages from users to generate on-demand article
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message
    user_text = user_message.text_html or user_message.caption_html

    if user_text:
        # Suggesting to generate an article
        prompt_text = f"Желаете сгенерировать статью на тему \"{user_text}\"?"
        await context.bot.send_message(
            chat_id=user_message.chat_id,
            text=prompt_text,
            reply_to_message_id=user_message.message_id,
            reply_markup=generate_article_reply_markup
        )


# Function to generate an article from a post
async def generate_article(text):
    try:
        prompt = f"""
        Расширь этот пост в статью объемом 2500-3000 символов,
        сохраняя общий смысл и соблюдая стиль профессиональной
        новостной журналистики. При этом сохраняй ссылки и html теги: \"{text}\"
        """

        tokens_estimate = len(prompt.split()) * 1.5

        # Manage rate limits before sending request
        can_proceed = await manage_rate_limit(tokens_estimate)
        if not can_proceed:
            return text  # Returns original text if limits exceed

        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.7
        )

        article = response.choices[0].message.content.strip()

        logging.info("Article generated successfully.")

        return article
    except Exception as e:
        logging.error(f"Error in generate_article: {e}")

        return text  # Returns original text in case of an error


# Function to generate on-demand article
async def on_demand_article(text):
    try:
        prompt = f"""
        Напиши обширную и исчерпывающую статью в профессиональном техническом стиле на заданную тему,
        используя следующий текст как тему и заголовок для статьи.
        При этом добавь html теги для стилизации текста статьи,
        только из этого списка: [<i>,<b>,<q>,<code>, <h1>, <h3>, <p>, <ul>, <li>]: \"{text}\".
        """

        tokens_estimate = len(prompt.split()) * 1.5

        # Manage rate limits before sending request
        can_proceed = await manage_rate_limit(tokens_estimate)
        if not can_proceed:
            return text  # Returns original text if limits exceed

        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.7
        )

        article = response.choices[0].message.content.strip()

        logging.info("On-demand article generated successfully.")

        return article
    except Exception as e:
        logging.error(f"Error in on_demand_article: {e}")

        return text  # Returns original text in case of an error


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
        db.addpost(
            "", query.message.text_html or query.message.caption_html, f.read())
        await query.edit_message_reply_markup()
    elif query.data.startswith('delete'):
        message_id = query.message.message_id
        await query.delete_message()
    elif query.data == 'expand':
        # Extract original text or caption to expand
        original_text = query.message.text_html or query.message.caption_html
        article_text = await generate_article(original_text)

        # Send the article as a new message with confirmation/delete buttons
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=article_text,
            reply_to_message_id=query.message.message_id,
            reply_markup=article_reply_markup
        )
    elif query.data == 'confirm_article':
        return
        raw = query.message.reply_to_message.photo[-1].file_id
        file_info = await context.bot.get_file(raw)
        f = BytesIO(await file_info.download_as_bytearray())
        db.addpost(
            "", query.message.reply_to_message.text_html or query.message.reply_to_message.caption_html, f.read(), query.message.text_html)

        await query.message.reply_to_message.edit_reply_markup()
        await query.edit_message_reply_markup()
    elif query.data == 'delete_article':
        await query.delete_message()
    elif query.data == 'generate_article':
        # Extracting user's original message
        original_message = query.message.reply_to_message
        user_text = original_message.text_html or original_message.caption_html

        # Generating an article
        article_text = await on_demand_article(user_text)

        # Sending an article depending on message type (plain text or media with caption)
        # if original_message.photo:
        #     await context.bot.send_photo(
        #         chat_id=original_message.chat_id,
        #         photo=original_message.photo[-1].file_id,
        #         caption=article_text,
        #         reply_to_message_id=original_message.message_id,
        #         reply_markup=article_reply_markup
        #     )
        # elif original_message.video:
        #     await context.bot.send_video(
        #         chat_id=original_message.chat.id,
        #         video=original_message.video.file_id,
        #         caption=article_text,
        #         reply_to_message_id=original_message.message.id,
        #         reply_markup=article_reply_markup
        #     )
        # else:
        #     await context.bot.send_message(
        #         chat_id=original_message.chat_id,
        #         text=article_text,
        #         reply_to_message_id=original_message.message_id,
        #         reply_markup=article_reply_markup
        #     )

        await context.bot.send_message(
            chat_id=original_message.chat_id,
            text=article_text,
            reply_to_message_id=original_message.message_id,
            reply_markup=article_reply_markup
        )

        # Deleting message with suggestion to generate an article
        await query.delete_message()


# Register handlers with more specific filters
application.add_handler(MessageHandler(
    filters.REPLY & filters.User(user_chat_ids), handle_reply
))
application.add_handler(MessageHandler(
    filters.User(news_bot_id) & ~filters.REPLY, handle_message
))
application.add_handler(MessageHandler(
    filters.TEXT | filters.PHOTO | filters.VIDEO & ~filters.REPLY, handle_user_message
))
application.add_handler(CallbackQueryHandler(button_handler))

# loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
logging.getLogger("httpx").setLevel(logging.WARNING)  # оффаем ненужные логи

# Launching the bot
if __name__ == '__main__':
    application.run_polling()
