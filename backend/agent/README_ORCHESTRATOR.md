# Disaster Orchestrator Agent

## 1. Overview
The Disaster Orchestrator Agent acts as the central hub and primary user interface for the DataLogFusion Multiagent system. Built for rural first-responder vehicle safety systems, it receives all natural language inquiries from dispatchers and intelligently routes them to specialized sub-agents based on the context of the question. By coordinating between the real-time Predictive Disaster Monitor and the historical Data Synthesis Agent, the Orchestrator provides a unified, seamless user experience.

## 2. Key features
- **Intelligent Query Routing:** Analyzes user prompts to determine if the question pertains to historical data synthesis or real-time event monitoring.
- **Unified Interface:** Allows dispatchers to interact with a single agent instead of manually choosing between specialized sub-agents.
- **Internal Agent Communication:** Wraps user queries into a `SharedAgentState` model and passes them to sub-agents, handling responses in the background before returning the final answer to the user.
- **Conversational Interface:** Uses the ASI:One LLM and Fetch.ai uAgents framework for natural language chat interactions.
- **Independent Operation:** Runs on a dedicated network port (`8003`) with a distinct Agentverse seed phrase, allowing it to communicate with the other agents running locally.

## 3. Usage instructions
Ensure your environment variables (such as `REDIS_HOST`, `ASI_API_KEY`, and `AGENTVERSE_KEY_ORCH`) are properly configured in `backend/.env`. You also need to have `agent.py` and `synthesis_agent.py` running in the background.

**Start the agent:**
```bash
python agent/orchestrator_agent.py
```

**Register the agent on Agentverse (run once):**
```bash
python agent/register_orchestrator.py
```

### Expected Inputs
The agent expects natural language questions about either real-time vehicle status or historical telemetry trends. 
Example inputs:
- *"What is the current vehicle status?"* (Routes to Monitor Agent)
- *"Did any crashes occur recently?"* (Routes to Monitor Agent)
- *"Summarize the vibration trends over the last 500 records."* (Routes to Synthesis Agent)
- *"What does the historical accelerometer data look like?"* (Routes to Synthesis Agent)

### Expected Outputs
The Orchestrator will instantly acknowledge your message, route your query in the background, and then return the specialized, detailed response from the appropriate sub-agent.

## 4. Use cases / examples
- **Emergency Dispatch:** A dispatcher asks "Has there been an accident?" The Orchestrator routes this to the Monitor Agent, which analyzes the live stream and responds with the real-time crash classification and Z-score analysis.
- **Historical Reporting:** A fleet manager asks "Can you synthesize the history for the fleet?" The Orchestrator routes this to the Synthesis Agent, which retrieves the last 500 rows and returns an analytical summary.

## 5. Limitations and known issues
- **Dependency on Sub-Agents:** The Orchestrator does not perform any data fetching or LLM processing itself; it relies entirely on `agent.py` and `synthesis_agent.py` being active and reachable.
- **Keyword Routing:** The Orchestrator currently routes based on simple keyword heuristics (e.g., "synthesize", "history", "trend"). Highly ambiguous questions might occasionally be misrouted.

## 6. Metadata and credits
- **Author:** DataLogFusion Team (UC Berkeley AI Hackathon 2026)
- **Version:** 1.0.0
- **Frameworks:** Built using the Fetch.ai `uagents` framework.
