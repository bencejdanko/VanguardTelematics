from uagents import Model

class SharedAgentState(Model):
    chat_session_id: str
    query: str
    user_sender_address: str
    result: str = ""
