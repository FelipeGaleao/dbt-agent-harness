"""Google ADK Adapter for Agentic dbt Development Harness."""

from __future__ import annotations

from typing import Any, List, Optional
from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from harness.core.config import HarnessConfig, get_config
from harness.core.registry import ToolRegistry
from harness.services.factory import build_harness_tool_registry


def create_adk_tools(registry: ToolRegistry) -> List[FunctionTool]:
    """Converts tools from the framework-agnostic registry into Google ADK FunctionTools."""
    adk_tools: List[FunctionTool] = []
    for tool_def in registry.list_tools():
        if callable(tool_def.handler):
            fn_tool = FunctionTool(tool_def.handler)
            # Ensure name and description align
            fn_tool.name = tool_def.name
            fn_tool.description = tool_def.description
            adk_tools.append(fn_tool)
    return adk_tools


def create_adk_agent(
    session_id: Optional[str] = None,
    model: str = "gemini-3.8-flash",
    config: Optional[HarnessConfig] = None,
) -> tuple[Agent, ToolRegistry, Any]:
    """Initializes a Google ADK Agent configured with all dbt Harness tools."""
    cfg = config or get_config()
    registry, services = build_harness_tool_registry(cfg, session_id=session_id)
    adk_tools = create_adk_tools(registry)

    agent_instruction = """You are an expert Autonomous dbt & Analytics Engineer specializing in DuckDB and Entity-Centric Data Modeling (ECM).
Your mission is to understand, extend, test, and improve the dbt project through iterative development.

Rules:
1. Always discover models, lineage, and read guidelines before creating or modifying models.
2. Adhere strictly to the Entity-Centric Data Modeling rules (dim_ wide entities, single grain, is_/has_ boolean flags, primary key unique and not-null tests).
3. ARCHITECTURAL LINEAGE RULE: Trusted models (dim_*, fct_*) MUST NEVER read from other trusted models! They must always read strictly from staging (stg_*) or raw.
4. Always inspect diffs using `propose_model_diff` before writing files.
5. After writing or modifying a model, execute validation via `validate_and_evaluate_model` or `execute_dbt`.
6. If validation fails, analyze the failures, revise the code, and re-test. Never hide errors or fabricate results.
"""

    agent = Agent(
        name="dbt_agentic_developer",
        description="Autonomous dbt & DuckDB Developer Agent",
        instruction=agent_instruction,
        model=model,
        tools=adk_tools,
    )

    return agent, registry, services

