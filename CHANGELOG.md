# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Full project documentation in `docs/`: architecture, technology stack, AI processing, configuration, deployment, and development guides.
- Rewritten `README.md` with system overview, diagrams, and a documentation index.
- `TELEGRAM_SESSION_PATH` setting; the Telethon session is stored in `sessions/` by default, which is the volume mounted by Docker Compose.
- Error handler for the bot that logs handler exceptions with tracebacks.
- The application shuts down when the Telethon client disconnects, so a supervisor can restart it.
- A second `SIGINT`/`SIGTERM` forces an immediate exit (for example during the interactive login prompt).
- Regression tests for every fix below (26 tests in total).

### Changed

- Editors receive review cards via `copy_message`, so every media type (including video) and the original formatting are preserved, and captionless media no longer shows a placeholder text.
- **Confirm** replaces the buttons with a "✅ Confirmed" marker instead of replacing the card text, so the reviewed content stays visible. Both **Confirm** and **Delete** check that the card was delivered to the editor who pressed the button.
- `/status` is restricted to configured editors. `/help` and `/status` use HTML formatting.
- `LOG_FILE` defaults to `logs/news_bot.log`, inside the volume mounted by Docker Compose.

### Fixed

- The Telethon client was never connected: `start()` and `disconnect()` were called without `await` inside the running event loop.
- Numeric channel IDs from `TELEGRAM_CHANNEL_IDS` were passed as strings, which Telethon interprets as phone numbers. They are now converted to integers, and whitespace around list items is trimmed.
- INFO logs from `NewsParser` and `TelegramBot` were dropped because their loggers were not children of the configured application logger.
- `/start`, `/help`, and `/status` were unreachable because the catch-all message handler was registered before the command handlers.
- After `SIGINT`/`SIGTERM` the components stopped but the process kept running.
- **Confirm** failed on photo and document cards (`edit_message_text` is not allowed on media messages).
- `.env` was not loaded for local runs although `python-dotenv` was a dependency. It is now loaded from the working directory at startup.
- Console logging no longer fails on terminals with legacy encodings (such as cp1251 on Windows) when messages contain emoji.
- Tests patched a different copy of the modules than the one under test, so the Telethon client was not actually mocked.

## [0.1.0] - 2025-11-16: Modular architecture

Rewrite of the two standalone scripts into an installable, testable, containerised application.

### Added

- `src/` package layout with separate `core`, `news_parser`, and `bot` packages and a `main.py` orchestrator.
- `NewsBotApplication`, which runs the Telethon listener and the Bot API bot concurrently in one event loop and shuts down on `SIGINT` and `SIGTERM`.
- Typed configuration (`TelegramConfig`, `OpenAIConfig`, `RateLimitConfig`, `AppConfig`) loaded from environment variables, with fail-fast validation.
- Configurable OpenAI model, `max_tokens`, and `temperature`.
- `RateLimiter` and `MessageTracker` as standalone, unit-tested classes.
- Centralised logging (`setup_logger`, `LoggerMixin`) with console and UTF-8 file output.
- Bot commands `/start`, `/help`, and `/status`.
- Handling of empty model responses and guards for incomplete Telegram updates.
- Test suite (pytest, pytest-asyncio) with mocked Telegram and OpenAI clients.
- `pyproject.toml` with `test` and `dev` extras, plus `requirements.txt`.
- `Dockerfile` (non-root user, health check) and `docker-compose.yml` (restart policy, volumes, resource limits).
- `.env.example` and an expanded `.gitignore`.

### Changed

- The rate limiter no longer sleeps when the budget is exhausted. It returns immediately and the pipeline falls back (classification assumes `News`, rewrite returns the original text), so the event loop is never blocked.
- Classification errors now default to `News` instead of returning an error string.

### Removed

- Root-level `news_bot.py` and `telegram_bot.py` scripts.

## 2025-03-24: Internationalisation

### Changed

- Classification and rewrite prompts translated to English. Labels are now `Advert`, `Opinion`, and `News`.
- The rewrite prompt now returns text in the **language of the source post** instead of always in Russian.
- Bot interface (buttons and placeholders) translated to English.

### Security

- Hard-coded credentials and identifiers removed from the source code and replaced with placeholders.

## 2024-09: Extended editorial features (experimental branch)

A feature branch explored richer editor tooling on top of the review workflow:

- **Reply-to-edit:** editors reply to a review card with text, a photo, or a video to replace its content in place.
- **Formatting preservation:** Telegram message entities (bold, italics, links, blockquotes) converted to HTML so formatting survives the pipeline.
- **Expand to article:** turns a post into a 2,500–3,000-character article in a professional news style.
- **On-demand articles:** any free-text message to the bot can become the topic of a generated long-form article.
- **AI translation:** translation of posts and articles into English that keeps HTML markup and links.
- **Persistence prototype:** storing approved posts and media in a database on **Confirm**.

These features are not part of the current `main` branch and are tracked on the roadmap.

## 2024-09-13 to 2024-09-15: Editorial review workflow

### Added

- A separate Bot API service (`telegram_bot.py`) built with python-telegram-bot.
- Relay architecture: the Telethon listener sends processed posts with their original media to the bot in a private chat, and the bot fans them out to editors.
- Inline **Confirm** and **Delete** actions, with per-editor message tracking so a delete only affects the editor's own copy.
- Persistent log files for both services.

### Changed

- Media is no longer downloaded and re-uploaded. Telegram copies it server-side and the bot refers to it by `file_id`.
- Opinion posts are routed to human review. Only advertising is filtered automatically.

## 2024-09-12: Initial pipeline

### Added

- A Telethon listener for a configured list of Telegram channels.
- AI classification of posts (advert, opinion, or news) with OpenAI `gpt-3.5-turbo`.
- AI deep rewrite that preserves meaning and direct quotations.
- Delivery of rewritten posts, including photos and videos, to a list of users through a Telegram bot.
- Request and token budgeting for the OpenAI API (per minute and per day).
