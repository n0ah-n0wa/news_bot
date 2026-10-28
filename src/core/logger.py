"""
Centralized logging configuration for the news bot application.
"""
import logging
import sys
from typing import Optional
from pathlib import Path

APP_LOGGER_NAME = "news_bot"


def setup_logger(
    name: str = APP_LOGGER_NAME,
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: Optional[str] = None
) -> logging.Logger:
    """
    Set up a logger with both file and console handlers.

    Args:
        name: Logger name.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Path to log file. If None, only console logging.
        log_format: Custom log format string.

    Returns:
        logging.Logger: Configured logger instance.
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Default log format
    if log_format is None:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    formatter = logging.Formatter(log_format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if log_file is specified)
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(
            getattr(logging, log_level.upper(), logging.INFO))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = APP_LOGGER_NAME) -> logging.Logger:
    """
    Get an existing logger instance.

    Args:
        name: Logger name.

    Returns:
        logging.Logger: Logger instance.
    """
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""

    @property
    def logger(self) -> logging.Logger:
        """
        Get logger for this class.

        The logger is a child of the application logger, so records
        propagate to the handlers configured by setup_logger().
        """
        return get_logger(
            f"{APP_LOGGER_NAME}.{self.__class__.__module__}.{self.__class__.__name__}")




