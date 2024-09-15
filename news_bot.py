import time
from telethon.sync import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon import events
import openai
import logging
import asyncio

# Configure logging to save to a file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("news_bot_log.log"),
        logging.StreamHandler()
    ]
)

# Access parameters
api_id = '20772977'
api_hash = '0bacdd9a8621f8f907a58ff3870219a5'
openai_api_key = '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'
bot_username = '@newewews_bot'

# API rate limits
MAX_TOKENS_PER_MINUTE = 40000
MAX_REQUESTS_PER_MINUTE = 3
MAX_REQUESTS_PER_DAY = 200

# Current usage tracking
token_usage = 0
request_count_minute = 0
request_count_day = 0
last_request_time = time.time()

# Initializing Telethon client
client = TelegramClient('session_name', api_id, api_hash)
openai.api_key = openai_api_key

# Channels list to monitor
channel_ids = [-1001479815768, -1001222869173, -1002401857796]


# managing API limits
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
        logging.info(f"Rate limit reached, waiting for {
                     wait_time:.2f} seconds...")
        await asyncio.sleep(wait_time)
        request_count_minute = 0
        token_usage = 0

    # Update counters
    token_usage += tokens_used
    request_count_minute += 1
    request_count_day += 1
    last_request_time = time.time()

    return True


# Handle new messages
@client.on(events.NewMessage(chats=channel_ids))
async def handler(event):
    message = event.message

    if message.text:
        logging.info(f"Message received: {message.text}...")

        # Check content type (Advertising, Opinion, News)
        content_type = await check_content_type(message.text)
        # Add 'Мнение' here to skip posts with personal opinion
        if content_type in ['Реклама']:
            logging.info(f"Skipping a message of a type: {content_type}")
            return

        # Rewriting text
        rewritten_text = await rewrite_text(message.text)

        # Forwarding message with media to telegram_bot
        await forward_message_to_bot(message, rewritten_text)


# Checking content type: Ad, Opinion, or News
async def check_content_type(text):
    try:
        prompt = f"""
        Определи, является ли данный текст рекламой, личным мнением или новостью: \"{text}\".
        Если реклама, ответь одним словом \"Реклама\". Если личное мнение, ответь \"Мнение\".
        Если новость, ответь \"Новость\".
        """
        # Approximate tokens count per request
        tokens_estimate = len(prompt.split()) * 1.5

        # Manage rate limits before sending request
        can_proceed = await manage_rate_limit(tokens_estimate)
        if not can_proceed:
            return "Request limit has been reached."

        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0
        )
        result = response.choices[0].message.content.strip()
        logging.info(f"Content type determined: {result}")

        return result
    except Exception as e:
        logging.error(f"Error in check_content_type: {e}")

        return f"Error in check_content_type: {e}"


# Rewriting the post while keeping direct quotes unchanged
async def rewrite_text(text):
    try:
        prompt = f"""
        Сделай глубокий рерайт следующего текста, но оставь общий смысл неизменным,
        а также сохрани прямые цитаты без изменений, если таковые в тексте есть.
        Обрати внимание, что результат ты должен вернуть на русском языке: \"{text}\"
        """
        # Approximate tokens count per request
        tokens_estimate = len(prompt.split()) * 1.5

        # Manage rate limits before sending request
        can_proceed = await manage_rate_limit(tokens_estimate)
        if not can_proceed:
            return text  # Return the original text if rate limits prevent rewriting

        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0
        )
        rewritten = response.choices[0].message.content.strip()
        logging.info("Text rewritten successfully.")

        return rewritten
    except Exception as e:
        logging.error(f"Error in rewrite_text: {e}")

        return text  # Return the original text if rewriting fails


async def forward_message_to_bot(message, rewritten_text):
    try:
        # Find the bot by username and forward the message
        bot_entity = await client.get_entity(bot_username)
        await client.send_message(bot_entity, rewritten_text, file=message.media)
        logging.info("Message successfully forwarded to bot.")
    except Exception as e:
        logging.error(f"Error when forwarding a message: {e}")


# Launching Telethon client
async def main():
    logging.info("Script running...")
    await client.start()
    await client.run_until_disconnected()

asyncio.run(main())
