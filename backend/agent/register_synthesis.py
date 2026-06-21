import os
import sys

from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
)

# Import the same config values to stay consistent
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from config import AGENT_SEED_PHRASE_SYNTH, AGENTVERSE_KEY_SYNTH

print("Registering Data Synthesis chat agent...")
register_chat_agent(
    "Predictive Data Synthesis",
    "https://asi1.ai/ai/predictivedisastermo",  # Use the same image/URL or a different one
    active=True,
    credentials=RegistrationRequestCredentials(
        agentverse_api_key=AGENTVERSE_KEY_SYNTH,
        agent_seed_phrase=AGENT_SEED_PHRASE_SYNTH,        
    ),
)
print("Data Synthesis Agent registered successfully.")
