from telethon.sync import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon import events
import openai
from telegram import Bot
import logging
import os
import time
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Access parameters
api_id = '20772977'
api_hash = '0bacdd9a8621f8f907a58ff3870219a5'
bot_token = '7354476983:AAG8judAhTygD-dMCZOvwcofHAZyNGdi5EY'
openai_api_key = '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'

# List of channel IDs to monitor & user chat IDs to send results to
# Ensure channel IDs have the -100 prefix
channel_ids = [-1001479815768, -1001222869173, -1002401857796]
user_chat_ids = [490748903, 452536082]

# Initializing clients
client = TelegramClient('session_name', api_id, api_hash)
bot = Bot(token=bot_token)
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
        а также сохрани прямые цитаты без изменений, если таковые в тексте есть: \"{text}\"
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


# Function to delete the downloaded media file when it's no longer needed
def delete_file(file_path):
    try:
        os.remove(file_path)
        logging.info(f"Deleted file: {file_path}")
    except Exception as e:
        logging.error(f"Error deleting file {file_path}: {e}")


# Event handler for new messages from the specified channels
@client.on(events.NewMessage(chats=channel_ids))
async def handler(event):
    message = event.message

    # Check if the message contains text
    if message.text:
        # Log the first 50 characters of the message
        logging.info(f"Received message: {message.text[:50]}...")

        # Check the type of content (Ad, Opinion, News)
        content_type = await check_content_type(message.text)
        if content_type in ['Реклама', 'Мнение']:
            logging.info(f"Skipping message of type: {content_type}")
            return

        # Check if there is any media in the message
        media = None
        try:
            if message.media:
                if isinstance(message.media, MessageMediaPhoto):
                    file = await client.download_media(message.media)
                    media = {'type': 'photo', 'file_path': file}
                    logging.info("Photo media downloaded.")
                elif isinstance(message.media, MessageMediaDocument) and message.media.document.mime_type.startswith('video'):
                    file = await client.download_media(message.media)
                    media = {'type': 'video', 'file_path': file}
                    logging.info("Video media downloaded.")
        except Exception as e:
            logging.error(f"Error downloading media: {e}")

        # Rewrite the post's text
        rewritten_text = await rewrite_text(message.text)

        # Send the media and rewritten text to the specified user chat IDs
        for chat_id in user_chat_ids:
            try:
                if media:
                    if media['type'] == 'photo':
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=open(media['file_path'], 'rb'),
                            caption=rewritten_text,
                        )
                        logging.info(f"Photo sent to chat {chat_id}.")
                    elif media['type'] == 'video':
                        await bot.send_video(
                            chat_id=chat_id,
                            video=open(media['file_path'], 'rb'),
                            caption=rewritten_text,
                        )
                        logging.info(f"Video sent to chat {chat_id}.")
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=rewritten_text,
                    )
                    logging.info(f"Message sent to chat {chat_id}.")
            except Exception as e:
                logging.error(f"Error sending message to chat {chat_id}: {e}")

        # Delete media file after sending to all users
        if media and media['file_path']:
            delete_file(media['file_path'])


# Start the client and keep the script running indefinitely
with client:
    logging.info("Starting the script...")
    logging.info("Waiting for messages in specified channels...")
    client.run_until_disconnected()
