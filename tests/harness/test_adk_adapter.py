"""Tests for Google ADK Adapter."""

import pytest
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from harness.adapters.google_adk import create_adk_agent, create_adk_tools
from harness.services.factory import build_harness_tool_registry


def test_create_adk_tools():
    registry, _ = build_harness_tool_registry()
    tools = create_adk_tools(registry)
    assert len(tools) >= 14
    assert all(isinstance(t, FunctionTool) for t in tools)
    tool_names = [t.name for t in tools]
    assert "discover_project" in tool_names
    assert "write_model_file" in tool_names
    assert "validate_and_evaluate_model" in tool_names


def test_create_adk_agent():
    agent, registry, services = create_adk_agent(session_id="session-test")
    assert isinstance(agent, Agent)
    assert agent.name == "dbt_agentic_developer"
    assert len(agent.tools) >= 14

