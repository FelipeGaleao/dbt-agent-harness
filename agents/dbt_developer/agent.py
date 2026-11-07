"""Google ADK Agent definition for adk web UI."""

from harness.adapters.google_adk import create_adk_agent

# ADK web CLI searches for `root_agent` in agent.py
agent, registry, services = create_adk_agent(
    session_id="adk-web-session",
    model="gemini-2.5-flash",
)
root_agent = agent
