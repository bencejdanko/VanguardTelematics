import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from models import SharedAgentState
from config import AGENT_SEED_PHRASE_ORCH, AGENT_SEED_PHRASE_DIS, AGENT_SEED_PHRASE_SYNTH

ANALYSIS_AGENT_ADDRESS = Agent(name="dummy1", seed=AGENT_SEED_PHRASE_DIS).address
SYNTHESIS_AGENT_ADDRESS = Agent(name="dummy2", seed=AGENT_SEED_PHRASE_SYNTH).address

orchestrator = Agent(
    name="Predictive-Disaster-Orchestrator-Agent",
    seed=AGENT_SEED_PHRASE_ORCH,
    port=8003,
    mailbox=True,
    publish_agent_details=True,
)

chat_proto = Protocol(spec=chat_protocol_spec)

@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    text = " ".join(
        item.text for item in msg.content if isinstance(item, TextContent)
    )
    ctx.logger.info(f"Received query: {text}")

    chat_session_id = str(ctx.session)
    state = SharedAgentState(
        chat_session_id=chat_session_id,
        query=text,
        user_sender_address=sender,
    )

    text_lower = text.lower()
    
    # Simple routing logic
    if any(keyword in text_lower for keyword in ["synthesize", "history", "past", "records", "pattern"]):
        await ctx.send(SYNTHESIS_AGENT_ADDRESS, state)
        ctx.logger.info(f"Routing to Synthesis Agent! ({SYNTHESIS_AGENT_ADDRESS})")
    else:
        # Default route to live analysis agent for status, disaster alerts, etc.
        await ctx.send(ANALYSIS_AGENT_ADDRESS, state)
        ctx.logger.info(f"Routing to Live Monitor Agent! ({ANALYSIS_AGENT_ADDRESS})")

@chat_proto.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass

orchestrator.include(chat_proto, publish_manifest=True)

@orchestrator.on_message(SharedAgentState)
async def handle_agent_response(ctx: Context, sender: str, state: SharedAgentState):
    ctx.logger.info(f"Received result from sub-agent: session={state.chat_session_id}")
    await ctx.send(
        state.user_sender_address,
        ChatMessage(
            timestamp=datetime.now(tz=timezone.utc),
            msg_id=uuid4(),
            content=[
                TextContent(type="text", text=state.result),
                EndSessionContent(type="end-session"),
            ],
        ),
    )

if __name__ == "__main__":
    orchestrator.run()
