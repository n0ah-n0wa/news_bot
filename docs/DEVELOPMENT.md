# Development Guide

This guide is for engineers working on the News Bot code base: setting up an environment, running and writing tests, following project conventions, and extending the system.

- [Environment Setup](#environment-setup)
- [Repository Layout](#repository-layout)
- [Import Conventions](#import-conventions)
- [Running the Application](#running-the-application)
- [Testing Strategy](#testing-strategy)
- [Code Quality](#code-quality)
- [Coding Conventions](#coding-conventions)
- [Common Development Tasks](#common-development-tasks)
- [Contribution Workflow](#contribution-workflow)

---

## Environment Setup

```bash
git clone https://github.com/n0ah-n0wa/news_bot.git
cd news_bot

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[dev]"          # runtime + pytest, coverage, black, flake8, mypy
```

| Extra    | Installs                                                  |
| -------- | --------------------------------------------------------- |
| *(none)* | Runtime dependencies only                                 |
| `test`   | pytest, pytest-asyncio, pytest-cov                        |
| `dev`    | Everything in `test`, plus black, flake8, mypy            |

## Repository Layout

```
src/
├── __init__.py            # Public API re-exports (used by tests)
├── main.py                # NewsBotApplication and main()
├── core/                  # config.py, logger.py: no Telegram or OpenAI imports
├── news_parser/           # NewsParser, RateLimiter: Telethon and OpenAI
└── bot/                   # TelegramBot, MessageTracker: python-telegram-bot
tests/
├── conftest.py            # Adds src/ to sys.path
└── test_sample.py         # Unit and smoke tests
```

Dependency direction is one-way: `main` → `news_parser`, `bot` → `core`. Feature packages never import each other. They are connected only through Telegram, as described in [ARCHITECTURE.md](ARCHITECTURE.md).

## Import Conventions

The project uses a **src layout**. Inside `src/`, modules import each other as top-level packages:

```python
from core.config import AppConfig
from core.logger import LoggerMixin
```

For these imports to resolve, `src/` must be importable as a root. Any of the following works:

| Context            | Mechanism                                                     |
| ------------------ | ------------------------------------------------------------- |
| Editable install   | `pip install -e .` maps `core`, `bot`, `news_parser` from `src/` |
| Docker image       | `PYTHONPATH=/app/src`                                         |
| Tests              | `tests/conftest.py` inserts `src/` into `sys.path`            |
| Entry point        | `src/main.py` inserts its own directory into `sys.path`       |
| Ad-hoc scripts     | `PYTHONPATH=src python ...`                                   |

`src/__init__.py` re-exports the public classes (`NewsParser`, `TelegramBot`, `RateLimiter`, `MessageTracker`, the config classes, and `NewsBotApplication`).

Tests import from the top-level packages (`from news_parser.news_bot import NewsParser`), not through `src`. Importing through `src` loads a second copy of each module (`src.news_parser.news_bot`), and `patch("news_parser.news_bot.TelegramClient")` would then have no effect on the class under test.

## Running the Application

```bash
python -m src.main      # .env in the working directory is loaded automatically
```

Tips for development:

- Use a **separate test bot** and a **private test channel** so experiments never reach real editors.
- Set `LOG_LEVEL=DEBUG` to see detailed processing logs.
- Lower `OPENAI_MAX_TOKENS` and keep the default rate limits to cap costs while iterating.

## Testing Strategy

```bash
pytest                                   # all tests
pytest -v                                # verbose
pytest tests/test_sample.py::TestRateLimiter -v
pytest --cov=src --cov-report=term-missing
pytest --cov=src --cov-report=html       # report in htmlcov/
```

### Principles

- **No network.** `TelegramClient`, the PTB `Application`, and `openai.chat.completions.create` are patched with `unittest.mock`. Tests are fast and deterministic and need no credentials.
- **Configuration through constructors.** Tests build `AppConfig` objects directly instead of mutating environment variables.
- **Async-aware.** Coroutines are tested with `@pytest.mark.asyncio`.

### Current coverage by area

| Test class          | What it verifies                                                                    |
| ------------------- | ----------------------------------------------------------------------------------- |
| `TestConfig`        | Dataclass construction and defaults; validation; list parsing; numeric channel IDs converted to `int`; loading from environment variables |
| `TestLogger`        | Component loggers propagate to the configured application logger                    |
| `TestRateLimiter`   | Initial state; counters increase; requests are rejected once the per-minute cap is hit |
| `TestMessageTracker`| Adding, removing, and looking up items per user, including missing items           |
| `TestNewsParser`    | Construction and session path; `start()`/`stop()` await the Telethon client; adverts are dropped; classification and rewrite with a mocked OpenAI response |
| `TestTelegramBot`   | Commands registered before the catch-all handler; fan-out with `copy_message` and tracking; **Confirm** edits only the keyboard; **Delete** permission check |
| `TestIntegration`   | Construction; a shutdown request or a client disconnect makes `start()` return, and both components are stopped |

### Writing a new test

Add the test as a method of the relevant test class, so it can use that class's `mock_config` fixture:

```python
class TestNewsParser:
    ...

    @pytest.mark.asyncio
    async def test_rewrite_falls_back_to_original_on_error(self, mock_config):
        with patch("news_parser.news_bot.TelegramClient"), \
             patch("news_parser.news_bot.openai.chat.completions.create",
                   side_effect=RuntimeError("API down")):
            parser = NewsParser(mock_config)
            assert await parser._rewrite_text("original") == "original"
```

Patch targets must name the module where an object is **used** (`news_parser.news_bot.TelegramClient`), not where it is defined.

### Suggested next tests

- Handler routing in `TelegramBot._handle_message` (relay sender versus other users)
- `/status` access control (editor versus non-editor)
- Fallback paths of `_check_content_type` and `_rewrite_text` when the budget is exhausted
- The per-minute window reset in `RateLimiter` (with a patched `time.time`)

## Code Quality

```bash
black src tests                  # format
flake8 src tests                 # lint
mypy src                         # type-check
```

## Coding Conventions

- **PEP 8**, formatted with black.
- **Type hints** on all public functions and methods.
- **Docstrings** on every module, class, and public method, with `Args` and `Returns` sections in Google style.
- **Logging** through `LoggerMixin` (`self.logger`) in classes. Never use `print` outside the entry point.
- **Configuration** only through `AppConfig`. No `os.getenv` calls outside `core/config.py`.
- **External calls** wrapped in `try/except` with a logged, defined fallback (see [ARCHITECTURE.md](ARCHITECTURE.md#error-handling-and-resilience)).
- **Secrets** never in code, tests, or logs.

## Common Development Tasks

### Add a configuration option

1. Add a typed field with a default to the right dataclass in `src/core/config.py`.
2. Read it in `load_config()` with `os.getenv("NEW_VARIABLE", "<default>")` and convert the type.
3. If it is mandatory, add it to `validate_config()`.
4. Document it in `.env.example` and [CONFIGURATION.md](CONFIGURATION.md).

### Add a bot command

```python
# src/bot/telegram_bot.py
def _setup_handlers(self):
    ...
    self.application.add_handler(CommandHandler("sources", self._handle_sources_command))

async def _handle_sources_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sources command."""
    if not update.message:
        return
    await update.message.reply_text("\n".join(self.config.telegram.channel_ids) or "No sources")
```

Within a handler group, PTB dispatches each update only to the **first** matching handler, and `filters.ALL` also matches command messages. Command handlers must therefore be registered before the catch-all `MessageHandler(filters.ALL)`, or the catch-all must be moved to a later group (`add_handler(handler, group=1)`).

### Add an inline action

1. Add an `InlineKeyboardButton` with distinct `callback_data` (for example `expand_<message_id>`) in `TelegramBot._review_keyboard`.
2. Handle that prefix in `_handle_button_click`, reusing `_parse_callback_message_id` and the `MessageTracker` permission check.
3. Keep `callback_data` under Telegram's 64-byte limit.

### Add an AI processing step

1. Add an `async` method to `NewsParser` that follows the pattern of `_rewrite_text`: build the prompt, estimate tokens, call `self.rate_limiter.manage_rate_limit`, call the model, handle empty responses and exceptions with a fallback.
2. Call it from `_handle_new_message` at the right point in the pipeline.
3. Add tests with a mocked OpenAI response and a mocked failure.
4. Document the prompt in [AI_PROCESSING.md](AI_PROCESSING.md).

## Contribution Workflow

1. Create a feature branch from `main`.
2. Make focused commits with descriptive messages.
3. Add or update tests and run `pytest`, `black`, `flake8`, and `mypy` locally.
4. Update the relevant documentation in `docs/` and add an entry to [CHANGELOG.md](../CHANGELOG.md).
5. Open a pull request that describes the motivation, the change, and how it was tested.
