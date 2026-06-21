from datetime import datetime
from uuid import uuid4
import json
import os
import redis.asyncio as aioredis
from dotenv import load_dotenv
 
from openai import OpenAI
from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
 
 
### Example Expert Assistant
 
## This chat example is a barebones example of how you can create a simple chat agent
## and connect to agentverse. In this example we will be prompting the ASI:One model to
## answer questions on a specific subject only. This acts as a simple placeholder for
## a more complete agentic system.
##
 
# the subject that this assistant is an expert in
subject_matter = "automobile predictive monitoring"

import sys

# Load environment variables
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from config import (
    REDIS_HOST, REDIS_PORT, REDIS_USERNAME, REDIS_PASSWORD,
    REDIS_LATEST_KEY as LATEST_KEY
)


client = OpenAI(
    # By default, we are using the ASI:One LLM endpoint and model
    base_url='https://api.asi1.ai/v1',
 
    # You can get an ASI:One api key by creating an account at https://asi1.ai/dashboard/api-keys
    api_key='sk_080743e20e5b451ba911b80366080bdf645fdb0730a24959ba02b4de971d78eb',
)
 
agent = Agent(
    name="Predictive-Disaster-Monitor-Agent",
    seed="UCB-AI-Hackathon-2026-Winner-Predictive-Disaster-Monitor-Agent",
    port=8001,
    mailbox=True,
    publish_agent_details=True,
)
 
# We create a new protocol which is compatible with the chat protocol spec. This ensures
# compatibility between agents
protocol = Protocol(spec=chat_protocol_spec)
 
async def fetch_latest_telemetry() -> dict:
    """Fetch the latest sensor reading from Redis."""
    try:
        r = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            username=REDIS_USERNAME,
            password=REDIS_PASSWORD,
            decode_responses=True,
        )
        data = await r.hgetall(LATEST_KEY)
        await r.aclose()
        return data
    except Exception as e:
        return {}

# We define the handler for the chat messages that are sent to your agent
@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # send the acknowledgement for receiving the message
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )
 
    # collect up all the text chunks
    text = ''
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text
 
    # query the model based on the user question
    telemetry = await fetch_latest_telemetry()
    telemetry_context = "No live telemetry data available right now."
    if telemetry:
        telemetry_context = f"Latest telemetry data: {json.dumps(telemetry, indent=2)}"

    response = 'I am afraid something went wrong and I am unable to answer your question at the moment'
    try:
        r = client.chat.completions.create(
            model="asi1",
            messages=[
                {"role": "system", "content": f"""
        You are a helpful assistant who only answers questions about {subject_matter}. If the user asks 
        about any other topics, you should politely say that you do not know about them.

        {telemetry_context}
                """},
                {"role": "user", "content": text},
            ],
            max_tokens=2048,
        )
 
        response = str(r.choices[0].message.content)
    except:
        ctx.logger.exception('Error querying model')
 
    # send the response back to the user
    await ctx.send(sender, ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[
            # we send the contents back in the chat message
            TextContent(type="text", text=response),
            # we also signal that the session is over, this also informs the user that we are not recording any of the
            # previous history of messages.
            EndSessionContent(type="end-session"),
        ]
    ))
 
 
@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    # we are not interested in the acknowledgements for this example, but they can be useful to
    # implement read receipts, for example.
    pass
 
 
# attach the protocol to the agent
agent.include(protocol, publish_manifest=True)
 
if __name__ == "__main__":
    agent.run()
 