import json
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

import redis.asyncio as aioredis
from openai import OpenAI
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from models import SharedAgentState

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from config import (
    REDIS_HOST, REDIS_PORT, REDIS_USERNAME, REDIS_PASSWORD,
    REDIS_STREAM_KEY, ASI_API_KEY, AGENT_SEED_PHRASE_SYNTH
)

client = OpenAI(
    base_url='https://api.asi1.ai/v1',
    api_key=ASI_API_KEY,
)

agent = Agent(
    name="Predictive-Data-Synthesis-Agent",
    seed=AGENT_SEED_PHRASE_SYNTH,
    port=8002,  # Use a different port than the analysis agent
    mailbox=True,
    publish_agent_details=True,
)

protocol = Protocol(spec=chat_protocol_spec)

async def _redis_client():
    return aioredis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        decode_responses=True, 
        socket_connect_timeout=30, 
        socket_timeout=30, 
        retry_on_timeout=True,
    )

async def fetch_historical_telemetry(limit: int = 500) -> list:
    """Fetch up to `limit` rows of historical telemetry data from Redis stream."""
    try:
        r = await _redis_client()
        # Fetch latest N entries
        entries = await r.xrevrange(REDIS_STREAM_KEY, max="+", min="-", count=limit)
        await r.aclose()
        
        if not entries:
            return []
            
        history = []
        for entry_id, fields in entries:
            # Add to list (converting the stream ID to a timestamp if desired)
            history.append({
                "stream_id": entry_id,
                "data": fields
            })
                
        return history
    except Exception as e:
        return []

async def process_synthesis_query(ctx: Context, query: str) -> str:
    ctx.logger.info(f"Processing synthesis query: {query}")
    ctx.logger.info("Fetching 500 rows of historical telemetry for synthesis...")
    history = await fetch_historical_telemetry(limit=500)

    if not history:
        context_str = "No historical telemetry data available in Redis stream."
    else:
        context_str = f"Latest {len(history)} telemetry rows (most recent first):\n" + json.dumps(history, indent=2)

    response = 'I am afraid something went wrong and I am unable to answer your question at the moment'
    try:
        r = client.chat.completions.create(
            model="asi1",
            messages=[
                {"role": "system", "content": f"""
You are the Predictive Data Synthesis Agent for a rural first-responder vehicle safety system.
Your role is to act as a grounded data synthesis agent. 
You have access to the last 500 rows of raw vehicle sensor data.

{context_str}

When the user asks a question:
1. Ground your answer STRICTLY in the 500 rows of data provided.
2. Summarize key trends, identify overall data behavior, and synthesize insights over the time window.
3. Be analytical and data-driven in your summary.
                """},
                {"role": "user", "content": query},
            ],
        )
        response = str(r.choices[0].message.content)
    except Exception:
        ctx.logger.exception('Error querying model')

    return response


@agent.on_message(SharedAgentState)
async def handle_shared_state(ctx: Context, sender: str, state: SharedAgentState):
    """Handler for messages routed through the Orchestrator."""
    response = await process_synthesis_query(ctx, state.query)
    state.result = response
    await ctx.send(sender, state)


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handler for direct user messages via Agentverse UI."""
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )

    text = " ".join(
        item.text for item in msg.content if isinstance(item, TextContent)
    )

    response = await process_synthesis_query(ctx, text)

    await ctx.send(sender, ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=response),
            EndSessionContent(type="end-session"),
        ]
    ))

@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass

agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
