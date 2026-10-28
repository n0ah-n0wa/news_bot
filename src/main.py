"""
Main entry point for the news bot application.
"""
import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import find_dotenv, load_dotenv  # noqa: E402

from bot.telegram_bot import TelegramBot  # noqa: E402
from news_parser.news_bot import NewsParser  # noqa: E402
from core.logger import setup_logger  # noqa: E402
from core.config import load_config, validate_config  # noqa: E402


class NewsBotApplication:
    """Main application class that coordinates all components."""

    def __init__(self):
        self.config = None
        self.logger = None
        self.news_parser: Optional[NewsParser] = None
        self.telegram_bot: Optional[TelegramBot] = None
        self.running = False
        self._shutdown_event: Optional[asyncio.Event] = None

    def setup(self):
        """Initialize the application components."""
        try:
            # Load .env from the working directory without overriding the existing environment
            load_dotenv(find_dotenv(usecwd=True))

            # Load configuration
            self.config = load_config()

            # Validate configuration
            if not validate_config(self.config):
                print(
                    "❌ Configuration validation failed. Please check your environment variables.")
                sys.exit(1)

            # Setup logging
            self.logger = setup_logger(
                name="news_bot",
                log_level=self.config.log_level,
                log_file=self.config.log_file
            )

            if self.logger:
                self.logger.info("🚀 Starting News Bot Application")
                self.logger.info(
                    f"Configuration loaded: {self.config.log_level} logging level")

            # Initialize components
            self.news_parser = NewsParser(self.config)
            self.telegram_bot = TelegramBot(self.config)

            if self.logger:
                self.logger.info("✅ Application setup completed")

        except Exception as e:
            print(f"❌ Failed to setup application: {e}")
            sys.exit(1)

    async def start(self) -> None:
        """
        Start all application components and run until shutdown is requested
        or the Telegram client disconnects.
        """
        try:
            if self._shutdown_event is None:
                self._shutdown_event = asyncio.Event()
            self.running = True
            if self.logger:
                self.logger.info("🔄 Starting application components...")

            # Check if components are properly initialized
            if self.news_parser is None or self.telegram_bot is None:
                raise RuntimeError(
                    "Components not properly initialized. Call setup() first.")

            await self.news_parser.start()
            await self.telegram_bot.start()

            if self.logger:
                self.logger.info("✅ All components are running")

            shutdown_task = asyncio.create_task(self._shutdown_event.wait())
            parser_task = asyncio.create_task(
                self.news_parser.run_until_disconnected())
            done, pending = await asyncio.wait(
                {shutdown_task, parser_task},
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()

            if parser_task in done and self.logger:
                error = parser_task.exception()
                if error:
                    self.logger.error(f"Telegram client failed: {error}, shutting down")
                else:
                    self.logger.warning("Telegram client disconnected, shutting down")

        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Error starting application: {e}")

    def request_shutdown(self) -> None:
        """Ask a running application to stop."""
        if self._shutdown_event is not None:
            self._shutdown_event.set()

    async def stop(self) -> None:
        """Stop all application components."""
        if not self.running:
            return

        if self.logger:
            self.logger.info("🛑 Stopping application components...")
        self.running = False

        try:
            # Stop components
            if self.news_parser is not None:
                try:
                    await self.news_parser.stop()
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Error stopping news parser: {e}")

            if self.telegram_bot is not None:
                try:
                    await self.telegram_bot.stop()
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Error stopping telegram bot: {e}")

            if self.logger:
                self.logger.info("✅ Application stopped successfully")

        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Error stopping application: {e}")

    def setup_signal_handlers(self):
        """
        Setup signal handlers for graceful shutdown.

        Must be called from within the running event loop.
        """
        loop = asyncio.get_running_loop()
        self._shutdown_event = asyncio.Event()
        signals_received = 0

        def signal_handler(signum, frame):
            nonlocal signals_received
            signals_received += 1
            # A second signal forces exit, e.g. while blocked on the Telethon login prompt
            if signals_received > 1:
                raise KeyboardInterrupt
            if self.logger:
                self.logger.info(
                    f"Received signal {signum}, initiating graceful shutdown "
                    "(send again to force exit)...")
            loop.call_soon_threadsafe(self.request_shutdown)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main application entry point."""
    # Consoles with legacy encodings (e.g. cp1251 on Windows) cannot encode emoji
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")

    app = NewsBotApplication()

    try:
        # Setup application
        app.setup()

        # Setup signal handlers for graceful shutdown
        app.setup_signal_handlers()

        # Start application
        await app.start()

    except KeyboardInterrupt:
        if app.logger:
            app.logger.info("Received keyboard interrupt")
    except Exception as e:
        if app.logger:
            app.logger.error(f"Unexpected error: {e}")
    finally:
        await app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
