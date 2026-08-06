"""
Logging configuration for NanoBio Studio backend.
Provides structured logging with loguru.
"""
import sys
from loguru import logger
from nanobio_studio.app.core.config import settings


def configure_logging() -> None:
    """Configure loguru logger with file and console handlers."""
    # Remove default handler
    logger.remove()

    # Add console handler with colored output
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
    )

    # Add file handler
    logger.add(
        "logs/nanobio_studio_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.log_level,
        rotation="500 MB",
        retention="7 days",
    )


def get_logger(name: str):
    """Get a logger instance for a module."""
    return logger.bind(module=name)
