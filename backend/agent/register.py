import sys
import os

# Add parent directory to sys.path so config can be imported
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from config import AGENTVERSE_KEY, AGENT_SEED_PHRASE

from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
)

if not AGENTVERSE_KEY:
    raise ValueError("Missing AGENTVERSE_KEY in .env file!")

print("Registering chat agent...")
register_chat_agent(
    "Disaster Predictor",
    "https://asi1.ai/ai/predictivedisastermo",
    active=True,
    credentials=RegistrationRequestCredentials(
        agentverse_api_key=AGENTVERSE_KEY,
        agent_seed_phrase=AGENT_SEED_PHRASE,        
    ),
)
print("Registration successful!")
