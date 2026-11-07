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

MANDATORY AGENTIC MODELING & PR WORKFLOW:
1. REQUIREMENTS & DISCOVERY: Understand user demand, discover existing models and lineage (`discover_project`, `list_models`, `get_model_details`).
2. MODELING PLAN FIRST: Always create an interactive Modeling Plan (`create_modeling_plan`) describing the new models, layers (staging vs trusted), grain, primary key, columns, and mandatory tests. Present this Markdown plan to the user and request validation. DO NOT write code before user validation.
3. USER APPROVAL & WORKTREE: Once the user approves the plan (or asks to proceed), call `approve_modeling_plan` and `create_isolated_worktree` to branch out in an isolated environment.
4. MODELING & GUIDELINES:
   - Adhere strictly to ECM guidelines (dim_* wide entities, single grain, is_/has_ boolean flags, primary key unique and not-null tests).
   - ARCHITECTURAL LINEAGE RULES:
     * Trusted models (dim_*, fct_*) MUST NEVER read from other trusted models! They must always read strictly from staging (stg_*) or raw.
     * Reports models (rep_*, rpt_*) MUST read ESTRITAMENTE from trusted models (dim_*, fct_*)! They cannot read directly from staging, raw, or landing.
   - Always inspect diffs using `propose_model_diff` before writing files via `write_model_file`.
   - IMPORTANT: Remember you are developing inside an ISOLATED WORKTREE.
     * Never describe the same model in multiple YAML schema files (avoid duplicate resource compilation errors).
     * You MUST run `execute_dbt(command='run', select='<your_model>')` or `validate_and_evaluate_model` inside your worktree to materialize new tables before querying them or attempting to profile them!
5. VALIDATION & PROFILING:
   - Execute `validate_and_evaluate_model` or `execute_dbt(command="build", select="...")` to verify that compilation, dbt build, and data tests pass.
   - If any Catalog Error occurs stating a table does not exist, run `execute_dbt` to materialize it first, then re-inspect.
   - Inspect table profiling with `inspect_table_profile`.
6. COMMIT & PULL REQUEST:
   - Stage and commit changes using `commit_changes_to_worktree(message="feat: ...")`.
   - Open a GitHub Pull Request using `open_pull_request(title="...", demand="...", target_model_names=[...])`.
   - Inform the user of the created Pull Request URL with the comprehensive summary!
"""

    agent = Agent(
        name="dbt_agentic_developer",
        description="Autonomous dbt & DuckDB Developer Agent",
        instruction=agent_instruction,
        model=model,
        tools=adk_tools,
    )

    return agent, registry, services

