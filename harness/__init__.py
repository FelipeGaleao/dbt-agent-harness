"""Top-level package for the Agentic dbt Harness."""

from harness.core.config import HarnessConfig, get_config
from harness.core.contracts import (
    ColumnMetadata,
    EntityDefinition,
    LineageGraph,
    ModelMetadata,
    ProjectOverview,
    QueryResult,
    ValidationReport,
)
from harness.core.registry import ToolRegistry
from harness.services.factory import build_harness_tool_registry

__all__ = [
    "HarnessConfig",
    "get_config",
    "ToolRegistry",
    "build_harness_tool_registry",
    "ModelMetadata",
    "ColumnMetadata",
    "LineageGraph",
    "EntityDefinition",
    "ProjectOverview",
    "QueryResult",
    "ValidationReport",
]

