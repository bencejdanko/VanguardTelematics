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

AGENT_SEED_PHRASE_DIS = get_env_var("AGENT_SEED_PHRASE_DIS")
AGENT_SEED_PHRASE_SYNTH = get_env_var("AGENT_SEED_PHRASE_SYNTH")
AGENT_SEED_PHRASE_ORCH = os.getenv("AGENT_SEED_PHRASE_ORCH", "UCB-AI-Hackathon-2026-Winner-Orchestrator-Agent")

AGENTVERSE_KEY = os.getenv("AGENTVERSE_KEY")
AGENTVERSE_KEY_DIS = os.getenv("AGENTVERSE_KEY_DIS")
AGENTVERSE_KEY_SYNTH = os.getenv("AGENTVERSE_KEY_SYNTH")
AGENTVERSE_KEY_ORCH = os.getenv("AGENTVERSE_KEY_ORCH", AGENTVERSE_KEY)
