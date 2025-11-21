from __future__ import annotations

import atexit
import contextlib
import os
import signal
import sys

# Disable telemetry/analytics to avoid PostHog timeouts in restricted networks
# MEM0_TELEMETRY is the official Mem0 env var (checked in mem0/memory/telemetry.py)
os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("POSTHOG_DISABLED", "1")
os.environ.setdefault("DO_NOT_TRACK", "1")

from dify_plugin import DifyPluginEnv, Plugin
from utils.constants import MAX_REQUEST_TIMEOUT
from utils.logger import get_logger
from utils.mem0_client import AsyncLocalClient

logger = get_logger(__name__)

plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=MAX_REQUEST_TIMEOUT))

def _graceful_shutdown() -> None:
    logger.info("Initiating graceful shutdown of Mem0 plugin")
    with contextlib.suppress(Exception):
        AsyncLocalClient.shutdown(timeout=3.0)
    logger.info("Graceful shutdown completed")

atexit.register(_graceful_shutdown)

def _on_term(signum: int, frame: object | None) -> None:  # noqa: ARG001
    logger.info("Received signal %s, shutting down", signum)
    _graceful_shutdown()
    sys.exit(0)

with contextlib.suppress(Exception):
    signal.signal(signal.SIGTERM, _on_term)

if __name__ == "__main__":
    try:
        logger.info("Starting Mem0 Dify plugin")
        plugin.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        _graceful_shutdown()
        sys.exit(0)
    except Exception:
        logger.exception("Unexpected error occurred during plugin execution")
        raise
