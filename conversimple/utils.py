"""
Logging and utility functions for Conversimple SDK.

Provides:
- Logging configuration
- Helper utilities
- Common constants
"""

import logging
import os
import sys
from typing import Optional


def setup_logging(
    level: Optional[str] = None,
    format_string: Optional[str] = None
) -> None:
    """
    Set up logging for the Conversimple SDK.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format_string: Custom log format string
    """
    # Get log level from environment or parameter
    log_level = level or os.getenv("CONVERSIMPLE_LOG_LEVEL", "INFO")
    
    # Default format string
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=format_string,
        stream=sys.stdout
    )
    
    # Set specific logger levels
    logger = logging.getLogger("conversimple")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Suppress noisy third-party loggers
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_environment_config() -> dict:
    """Get configuration from environment variables."""
    return {
        "api_key": os.getenv("CONVERSIMPLE_API_KEY"),
        "customer_id": os.getenv("CONVERSIMPLE_CUSTOMER_ID"),
        "platform_url": os.getenv(
            "CONVERSIMPLE_PLATFORM_URL", 
            "ws://localhost:4000/sdk/websocket"
        ),
        "log_level": os.getenv("CONVERSIMPLE_LOG_LEVEL", "INFO"),
        "heartbeat_interval": int(os.getenv("CONVERSIMPLE_HEARTBEAT_INTERVAL", "30")),
        "max_reconnect_attempts": int(os.getenv("CONVERSIMPLE_MAX_RECONNECT_ATTEMPTS", "5"))
    }


# Constants
DEFAULT_PLATFORM_URL = "ws://localhost:4000/sdk/websocket"
DEFAULT_HEARTBEAT_INTERVAL = 30
DEFAULT_MAX_RECONNECT_ATTEMPTS = 5
DEFAULT_TOOL_TIMEOUT = 30