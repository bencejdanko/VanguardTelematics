"""
config.py
---------
DataLogFusion Backend — Configuration Manager

Loads, parses, and validates all environment variables.
"""

import os
import sys
import logging

# Set up logging for configuration loading
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("datalogfusion.config")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed; relying on system environment variables.")

def get_env_str(name: str) -> str:
    """Gets an environment variable as string, ensuring it is not empty."""
    val = os.getenv(name)
    if not val:
        raise ValueError(f"Required environment variable '{name}' is empty or not set.")
    return val

def get_env_int(name: str) -> int:
    """Gets an environment variable as integer, ensuring it is a valid integer."""
    val_str = os.getenv(name)
    if not val_str:
        raise ValueError(f"Required environment variable '{name}' is empty or not set.")
    try:
        return int(val_str)
    except ValueError as e:
        raise ValueError(f"Required environment variable '{name}' must be an integer. Got: '{val_str}'") from e

# Load and validate environment variables
try:
    REDIS_HOST = get_env_str("REDIS_HOST")
    REDIS_PORT = get_env_int("REDIS_PORT")
    REDIS_USERNAME = get_env_str("REDIS_USERNAME")
    REDIS_PASSWORD = get_env_str("REDIS_PASSWORD")
    STREAM_KEY = get_env_str("REDIS_STREAM_KEY")
    STREAM_MAXLEN = get_env_int("REDIS_STREAM_MAXLEN")

    # API Server configuration
    API_HOST = get_env_str("API_HOST")
    API_PORT = get_env_int("API_PORT")

    # Integration keys (optional)
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

    logger.info("Configuration successfully loaded and validated.")
except ValueError as err:
    logger.critical(f"Configuration validation failed: {err}")
    sys.exit(f"Configuration validation failed: {err}")

