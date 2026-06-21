# Predictive Data Synthesis Agent

## 1. Overview
The Predictive Data Synthesis Agent is a grounded Large Language Model (LLM) agent built for rural first-responder vehicle safety systems. Unlike traditional real-time alert systems, this agent automatically synthesizes and summarizes large batches of historical vehicle telemetry data directly from a Redis data stream. It is highly useful for identifying broad data trends, anomalies, and overall vehicle behavior over a specified time window, complementing real-time trigger detection with deep historical context.

## 2. Key features
- **Grounded Data Synthesis:** Strictly grounds its LLM responses in the raw telemetry data provided, avoiding hallucinations.
- **Batch Processing:** Fetches and analyzes up to 500 consecutive sensor readings from the live Redis Stream (`/data/mems`).
- **Conversational Interface:** Uses the ASI:One LLM and Fetch.ai uAgents framework for natural language chat interactions.
- **Independent Operation:** Runs concurrently with the real-time Analysis Agent, operating on a separate network port (`8002`) and utilizing a distinct Agentverse seed phrase.

## 3. Usage instructions
Ensure your environment variables (such as `REDIS_HOST`, `ASI_API_KEY`, and `AGENTVERSE_KEY`) are properly configured in `backend/.env`.

**Start the agent:**
```bash
python agent/synthesis_agent.py
```

**Register the agent on Agentverse (run once):**
```bash
python agent/register_synthesis.py
```

### Expected Inputs
The agent expects natural language questions about historical telemetry trends. 
Example inputs:
- *"What does the accelerometer data look like over the last few minutes?"*
- *"Summarize the vibration trends from the recent data for vehicle V-001."*

### Expected Outputs
A synthesized, analytical response summarizing the provided 500 rows of telemetry data.

## 4. Use cases / examples
- **Post-Incident Analysis:** Emergency responders can query the agent to get a summarized view of vehicle behavior leading up to or immediately following a crash.
- **Routine Diagnostics:** Fleet managers can ask for a quick summary of vehicle telemetry to spot long-term degradation or sustained rotation anomalies.
- **Example Interaction:**
  - **User:** "Summarize the recent vibration trends."
  - **Agent:** "Based on the last 500 telemetry rows, vibration levels averaged 1.2 m/s² with minor spikes up to 2.5 m/s². The overall trend remains stable, with no sustained anomalies detected across the analyzed time window."

## 5. Limitations and known issues
- **Context Window Limits:** The agent currently synthesizes up to 500 rows of data at a time. Attempting to ingest significantly larger datasets may exceed the LLM's context window.
- **Not for Real-Time Triggers:** This agent is designed strictly for historical data synthesis and trend analysis, not instant alert generation. Use the primary Analysis Agent (`agent.py`) for real-time crash detection.
- **Data Retention:** The agent relies on the `/data/mems` Redis stream retaining historical data. If the stream is aggressively truncated, older data will not be available for synthesis.

## 6. Metadata and credits
- **Author:** DataLogFusion Team (UC Berkeley AI Hackathon 2026)
- **Version:** 1.0.0
- **Frameworks:** Built using the Fetch.ai `uagents` framework and the `OpenAI` Python SDK powered by the ASI:One model.
