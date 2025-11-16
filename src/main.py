"""
Main entry point for the news bot application.
"""
from bot.telegram_bot import TelegramBot
from news_parser.news_bot import NewsParser
from core.logger import setup_logger
from core.config import load_config, validate_config
import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))


class NewsBotApplication:
    """Main application class that coordinates all components."""

    def __init__(self):
        self.config = None
        self.logger = None
        self.news_parser: Optional[NewsParser] = None
        self.telegram_bot: Optional[TelegramBot] = None
        self.running = False

    def setup(self):
        """Initialize the application components."""
        try:
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
        """Start all application components."""
        try:
            self.running = True
            if self.logger:
                self.logger.info("🔄 Starting application components...")

            # Check if components are properly initialized
            if self.news_parser is None or self.telegram_bot is None:
                raise RuntimeError(
                    "Components not properly initialized. Call setup() first.")

            # Start both components concurrently
            await asyncio.gather(
                self.news_parser.start(),
                self.telegram_bot.start()
            )

        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Error starting application: {e}")
            if self.running:
                await self.stop()

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
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            if self.logger:
                self.logger.info(
                    f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main application entry point."""
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
