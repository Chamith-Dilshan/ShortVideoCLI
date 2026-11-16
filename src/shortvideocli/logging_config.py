"""Logging configuration for ShortVideoCLI."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from shortvideocli.config import Settings


def setup_logging(settings: Settings) -> Path:
    """Configure console and file logging.

    Relative log paths are resolved from the project working directory.
    Existing root handlers are replaced to prevent duplicate messages.

    Args:
        settings: Validated application settings.

    Returns:
        The absolute path to the application log file.

    Raises:
        OSError: If the log directory or file cannot be created.
    """
    log_path = settings.log_file.expanduser()

    if not log_path.is_absolute():
        log_path = Path.cwd() / log_path

    log_path = log_path.resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(settings.log_level)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(settings.log_level)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(settings.log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.getLogger("shortvideocli").info(
        "Logging initialized. File: %s",
        log_path,
    )

    return log_path
