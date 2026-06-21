import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

def get_env_var(key: str) -> str:
    val = os.getenv(key)
    if val is None:
        raise ValueError(f"Missing required environment variable: {key}")
    return val

REDIS_HOST = get_env_var("REDIS_HOST")
REDIS_PORT = int(get_env_var("REDIS_PORT"))
REDIS_USERNAME = get_env_var("REDIS_USERNAME")
REDIS_PASSWORD = get_env_var("REDIS_PASSWORD")
REDIS_STREAM_KEY = get_env_var("REDIS_STREAM_KEY")
REDIS_LATEST_KEY = get_env_var("REDIS_LATEST_KEY")

API_HOST = get_env_var("API_HOST")
API_PORT = int(get_env_var("API_PORT"))
REDIS_STREAM_MAXLEN = int(get_env_var("REDIS_STREAM_MAXLEN"))
DEEPGRAM_API_KEY = get_env_var("DEEPGRAM_API_KEY")

ASI_API_KEY = get_env_var("ASI_API_KEY")
AGENT_SEED_PHRASE = get_env_var("AGENT_SEED_PHRASE")
AGENTVERSE_KEY = os.getenv("AGENTVERSE_KEY")
