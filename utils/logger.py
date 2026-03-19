"""Unified logger configuration for Mem0 Dify Plugin.

This module provides a centralized logger configuration that ensures all logs
are properly output to the Dify plugin container using the official plugin logger handler.
"""

import logging
import os

from dify_plugin.config.logger_format import plugin_logger_handler


def _resolve_log_level() -> int:
    """Resolve the log level from the global LOG_LEVEL environment variable.

    Supported values: DEBUG, INFO, WARNING, ERROR.
    Falls back to DEBUG when the variable is missing or invalid.
    """
    raw_level = os.getenv("LOG_LEVEL", "DEBUG").strip().upper()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    return level_map.get(raw_level, logging.DEBUG)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with Dify plugin handler configured.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Configured logger instance

    """
    logger = logging.getLogger(name)
    log_level = _resolve_log_level()
    logger.setLevel(log_level)
    # Only add handler if not already added to avoid duplicate logs
    if not logger.handlers:
        logger.addHandler(plugin_logger_handler)
    plugin_logger_handler.setLevel(log_level)
    return logger
