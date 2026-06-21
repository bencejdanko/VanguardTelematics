import sys
import os

# Add parent directory to sys.path so config can be imported
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from config import AGENTVERSE_KEY_ORCH, AGENT_SEED_PHRASE_ORCH

from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
)

if not AGENTVERSE_KEY_ORCH:
    raise ValueError("Missing AGENTVERSE_KEY_ORCH in .env file!")

print("Registering orchestrator chat agent...")
register_chat_agent(
    "Disaster Orchestrator",
    "https://asi1.ai/ai/predictivedisastermo",
    active=True,
    credentials=RegistrationRequestCredentials(
        agentverse_api_key=AGENTVERSE_KEY_ORCH,
        agent_seed_phrase=AGENT_SEED_PHRASE_ORCH,        
    ),
)
print("Registration successful!")
