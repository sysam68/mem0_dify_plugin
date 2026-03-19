"""Unified logger configuration for Mem0 Dify Plugin.

This module provides a centralized logger configuration that ensures all logs
are properly output to the Dify plugin container using the official plugin logger handler.
"""

import logging
import os

from dify_plugin.config.logger_format import plugin_logger_handler


def _read_bool_env(name: str) -> bool | None:
    """Read a boolean-like environment variable."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return None

    normalized = raw_value.strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    return None


def is_debug_environment() -> bool:
    """Return True when Dify debug flags require verbose plugin logging."""
    return _read_bool_env("DEBUG") is True or _read_bool_env("FLASK_DEBUG") is True


def _resolve_log_level() -> int:
    """Resolve the effective log level for the plugin.

    Precedence:
    1. Dify debug flags (`DEBUG=True` or `FLASK_DEBUG=True`) force DEBUG.
    2. `LOG_LEVEL` supports DEBUG, INFO, WARNING, ERROR.
    3. Fallback to DEBUG when nothing valid is configured.
    """
    if is_debug_environment():
        return logging.DEBUG

    raw_level = os.getenv("LOG_LEVEL", "DEBUG").strip().upper()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    return level_map.get(raw_level, logging.DEBUG)


def format_exception(error: BaseException) -> str:
    """Return a compact, explicit exception description for logs."""
    return f"{type(error).__name__}: {error!s}"


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
