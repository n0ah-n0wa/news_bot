# News Bot

A professional Telegram bot application that monitors news channels, processes content with AI, and forwards relevant news to users with interactive controls.

## Architecture

The project follows a modular, professional structure:

```
news-bot/
├── src/
│   ├── __init__.py         # Package exports
│   ├── bot/                # Telegram bot (working with the admin)
│   │   ├── __init__.py
│   │   └── telegram_bot.py
│   ├── news_parser/        # Channel monitoring and rewriting logic
│   │   ├── __init__.py
│   │   └── news_bot.py
│   ├── core/               # General utilities (configs, logging, rate limiter)
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── logger.py
│   └── main.py             # Entry point
├── tests/                  # Test files
│   ├── __init__.py
│   ├── conftest.py         # Pytest configuration
│   └── test_sample.py
├── .env.example            # Example environment variables
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Package configuration
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose configuration
└── README.md
```

## Features

- **Channel Monitoring**: Automatically monitors specified Telegram channels for new messages
- **AI Content Processing**: Uses OpenAI GPT to classify and rewrite news content
- **Smart Filtering**: Filters out advertisements and personal opinions, keeping only news
- **Interactive Controls**: Users can confirm or delete forwarded messages
- **Rate Limiting**: Built-in API rate limiting to prevent exceeding OpenAI limits
- **Professional Logging**: Comprehensive logging system with file and console output
- **Docker Support**: Ready for containerized deployment
- **Modular Design**: Clean separation of concerns for maintainability

## Prerequisites

- Python 3.8+
- Telegram API credentials (from [my.telegram.org](https://my.telegram.org/apps))
- OpenAI API key (from [platform.openai.com](https://platform.openai.com/api-keys))
- Docker (optional, for containerized deployment)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd news-bot
```

### 2. Install Dependencies

**Option A: Using pip (recommended for development)**
```bash
pip install -e .
```

**Option B: Using requirements.txt**
```bash
pip install -r requirements.txt
```

**For development with testing:**
```bash
pip install -e ".[test]"
```

### 3. Configuration

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your actual credentials:

   ```env
   # Telegram API Configuration
   TELEGRAM_API_ID=your_telegram_api_id
   TELEGRAM_API_HASH=your_telegram_api_hash

   # Telegram Bot Configuration
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_BOT_USERNAME=your_bot_username
   TELEGRAM_NEWS_BOT_ID=your_news_bot_account_id
   TELEGRAM_USER_CHAT_IDS=user_id_1,user_id_2,user_id_3
   TELEGRAM_CHANNEL_IDS=channel_id_1,channel_id_2,channel_id_3

   # OpenAI Configuration
   OPENAI_API_KEY=your_openai_api_key
   ```

### 4. Get Required IDs

#### Telegram API Credentials

1. Go to [my.telegram.org](https://my.telegram.org/apps)
2. Create a new application
3. Get your `api_id` and `api_hash`

#### Bot Token

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot with `/newbot`
3. Get your bot token

#### User and Channel IDs

1. **User Chat IDs**: Message [@userinfobot](https://t.me/userinfobot) to get your user ID
2. **Channel IDs**: Use [@getidsbot](https://t.me/getidsbot) or forward a message from the channel to get the channel ID
3. **News Bot ID**: This is the user ID of the account that will send messages to your bot

## Usage

### Local Development

```bash
# Run the application
python -m src.main

# Or if installed as package:
python src/main.py
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# Run in background
docker-compose up -d --build
```

### Docker Commands

```bash
# Build the image
docker build -t news-bot .

# Run the container
docker run --env-file .env news-bot

# View logs
docker-compose logs -f news-bot
```

## Testing

```bash
# Install test dependencies (if not already installed)
pip install -e ".[test]"

# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_sample.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Configuration Options

### Environment Variables

| Variable                  | Description                     | Default         |
| ------------------------- | ------------------------------- | --------------- |
| `TELEGRAM_API_ID`         | Telegram API ID                 | Required        |
| `TELEGRAM_API_HASH`       | Telegram API Hash               | Required        |
| `TELEGRAM_BOT_TOKEN`      | Bot token from @BotFather       | Required        |
| `TELEGRAM_BOT_USERNAME`   | Bot username                    | Required        |
| `TELEGRAM_NEWS_BOT_ID`    | News bot account ID             | Required        |
| `TELEGRAM_USER_CHAT_IDS`  | Comma-separated user IDs        | Required        |
| `TELEGRAM_CHANNEL_IDS`    | Comma-separated channel IDs     | Required        |
| `OPENAI_API_KEY`          | OpenAI API key                  | Required        |
| `OPENAI_MODEL`            | OpenAI model to use             | `gpt-3.5-turbo` |
| `OPENAI_MAX_TOKENS`       | Max tokens per request          | `500`           |
| `OPENAI_TEMPERATURE`      | Response randomness             | `0.0`           |
| `MAX_TOKENS_PER_MINUTE`   | Rate limit: tokens per minute   | `40000`         |
| `MAX_REQUESTS_PER_MINUTE` | Rate limit: requests per minute | `3`             |
| `MAX_REQUESTS_PER_DAY`    | Rate limit: requests per day    | `200`           |
| `LOG_LEVEL`               | Logging level                   | `INFO`          |
| `LOG_FILE`                | Log file path                   | `news_bot.log`  |

## Development

### Project Structure

- **`src/core/`**: Core utilities (configuration, logging)
- **`src/bot/`**: Telegram bot implementation
- **`src/news_parser/`**: News monitoring and processing
- **`src/main.py`**: Application entry point
- **`tests/`**: Test files

### Adding New Features

1. **New Bot Commands**: Add handlers in `src/bot/telegram_bot.py`
2. **New Content Processing**: Extend classes in `src/news_parser/`
3. **Configuration**: Add new settings to `src/core/config.py`
4. **Logging**: Use the `LoggerMixin` class for consistent logging

### Code Style

- Follow PEP 8 guidelines
- Use type hints
- Add docstrings to all functions and classes
- Write tests for new functionality

## Logging

The application provides comprehensive logging:

- **Console Output**: Real-time logs in the terminal
- **File Output**: Persistent logs saved to `news_bot.log`
- **Structured Logging**: Consistent format across all components
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL

## Troubleshooting

### Common Issues

1. **"Configuration validation failed"**

   - Check that all required environment variables are set
   - Verify API keys and IDs are correct

2. **"Rate limit reached"**

   - The bot has hit OpenAI rate limits
   - Wait for the rate limit window to reset
   - Consider adjusting rate limit settings

3. **"Message not forwarded"**

   - Check that user chat IDs are correct
   - Verify bot has permission to send messages to users

4. **"Channel not monitored"**
   - Ensure channel IDs are correct
   - Check that the bot has access to the channels

### Debug Mode

Enable debug logging by setting:

```env
LOG_LEVEL=DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:

- Create an issue in the repository
- Check the troubleshooting section
- Review the logs for error messages

## Changelog

### Version 1.0.0

- Initial release
- Modular architecture
- Docker support
- Comprehensive logging
- Rate limiting
- Interactive message controls




