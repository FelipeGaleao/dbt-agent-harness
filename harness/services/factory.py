"""Harness Services Factory and Default Tool Registry setup."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from harness.core.config import HarnessConfig, get_config
from harness.core.registry import ToolRegistry
from harness.evals.evaluators import DeterministicEvaluator
from harness.evals.reports import ValidationReporter
from harness.services.dbt_runner import DbtRunner
from harness.services.discovery import DiscoveryService
from harness.services.duckdb_inspector import DuckDBInspector
from harness.services.guidelines import GuidelinesService
from harness.services.workspace import WorkspaceManager
from harness.sessions.models import SessionRecord
from harness.sessions.store import SQLiteSessionStore


def build_harness_tool_registry(
    config: Optional[HarnessConfig] = None,
    session_id: Optional[str] = None,
) -> tuple[ToolRegistry, Dict[str, Any]]:
    """Builds the complete deterministic tool registry and services dictionary."""
    cfg = config or get_config()
    discovery = DiscoveryService(cfg)
    guidelines = GuidelinesService(cfg)
    workspace = WorkspaceManager(cfg)
    dbt_runner = DbtRunner(cfg)
    duckdb_inspector = DuckDBInspector(cfg)
    evaluator = DeterministicEvaluator(cfg, dbt_runner, guidelines, duckdb_inspector, workspace)
    session_store = SQLiteSessionStore(cfg)

    registry = ToolRegistry()

    # 1. Project Discovery Tools
    def discover_project() -> Dict[str, Any]:
        """Discover overall dbt project architecture, layers, and discovered entities."""
        return discovery.discover_project().model_dump()

    def list_models(layer: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all models in the dbt project, optionally filtered by architectural layer (landing, raw, staging, trusted)."""
        models = discovery.list_models(layer=layer)
        return [m.model_dump() for m in models]

    def get_model_details(model_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve detailed model metadata including columns, descriptions, tests, and SQL."""
        m = discovery.get_model_details(model_name)
        return m.model_dump() if m else None

    def get_model_lineage(model_name: str) -> Dict[str, Any]:
        """Retrieve upstream and downstream dependency lineage for a given model."""
        return discovery.get_model_lineage(model_name).model_dump()

    def get_entity_definitions() -> List[Dict[str, Any]]:
        """Discover existing Entity-Centric business entities from the trusted layer."""
        entities = discovery.get_entity_definitions()
        return [e.model_dump() for e in entities]

    # 2. Guidelines & Policies Tools
    def get_guidelines() -> str:
        """Get the full Entity-Centric Data Modeling (ECM) architectural guideline text."""
        return guidelines.get_raw_guidelines()

    def check_guidelines_compliance(
        model_name: str,
        sql_content: str,
        yaml_content: Optional[str] = None,
        layer: str = "trusted",
    ) -> List[Dict[str, Any]]:
        """Check deterministic guideline compliance (naming, grain, PK tests, boolean flags) on proposed code."""
        results = guidelines.validate_model_compliance(model_name, sql_content, yaml_content, layer)
        return [r.model_dump() for r in results]

    # 3. Workspace Management Tools
    def read_model_file(relative_path: str) -> str:
        """Read existing SQL or YAML model file from models/ directory."""
        return workspace.read_model_file(relative_path)

    def propose_model_diff(relative_path: str, new_content: str) -> str:
        """Inspect unified diff between current file content and proposed changes before applying."""
        return workspace.propose_diff(relative_path, new_content)

    def write_model_file(relative_path: str, content: str) -> Dict[str, Any]:
        """Create or modify a model SQL or YAML file within models/ directory safely."""
        res = workspace.write_model_file(relative_path, content)
        if session_id:
            session = session_store.get_session(session_id)
            if session:
                if relative_path not in session.modified_models:
                    session.modified_models.append(relative_path)
                session.current_revision += 1
                session_store.save_session(session)
        return res.model_dump()

    def delete_model_file(relative_path: str) -> Dict[str, Any]:
        """Safely delete a model SQL or YAML file from models/ directory."""
        res = workspace.delete_model_file(relative_path)
        if session_id:
            session = session_store.get_session(session_id)
            if session:
                if f"deleted:{relative_path}" not in session.modified_models:
                    session.modified_models.append(f"deleted:{relative_path}")
                session.current_revision += 1
                session_store.save_session(session)
        return res.model_dump()

    def delete_model(model_name: str, layer: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Delete a dbt model and its associated schema/SQL files from the project.
        Automatically finds the model across layers (or in a specified layer) and removes its definition.
        """
        changes = workspace.delete_model(model_name=model_name, layer=layer)
        if session_id:
            session = session_store.get_session(session_id)
            if session:
                for c in changes:
                    if f"deleted:{c.path}" not in session.modified_models:
                        session.modified_models.append(f"deleted:{c.path}")
                session.current_revision += 1
                session_store.save_session(session)
        return [c.model_dump() for c in changes]

    def revert_model_file(relative_path: str) -> bool:
        """Revert the most recent change made to a model file in this session."""
        return workspace.revert_file(relative_path)

    # 4. dbt Execution Tools
    def execute_dbt(
        command: str,
        select: Optional[str] = None,
        timeout_seconds: float = 60.0,
    ) -> Dict[str, Any]:
        """Execute a controlled dbt command (compile, run, test, build) with structured results."""
        res = dbt_runner.execute(command=command, select=select, timeout_seconds=timeout_seconds)
        return res.model_dump()

    # 5. DuckDB Inspection Tools
    def query_database(sql: str, limit: int = 50) -> Dict[str, Any]:
        """Execute a read-only bounded SQL query against DuckDB for data inspection."""
        res = duckdb_inspector.execute_query(sql=sql, limit=limit)
        return res.model_dump()

    def inspect_table_profile(table_name: str, schema_name: Optional[str] = None) -> Dict[str, Any]:
        """Inspect table schema, row count, null rates, and preview sample rows."""
        try:
            row_count = duckdb_inspector.get_row_count(table_name, schema=schema_name)
            null_rates = duckdb_inspector.inspect_null_rates(table_name, schema=schema_name)
            preview = duckdb_inspector.preview_table(table_name, schema=schema_name, limit=3)
            return {
                "table": f"{schema_name}.{table_name}" if schema_name else table_name,
                "row_count": row_count,
                "null_rates": null_rates,
                "preview_columns": preview.columns,
                "preview_sample_rows": preview.rows,
            }
        except Exception as e:
            return {
                "table": f"{schema_name}.{table_name}" if schema_name else table_name,
                "error": str(e),
                "suggestion": f"Check if table exists in schema '{schema_name}'. You can list tables using query_database."
            }

    def check_pk_uniqueness(table_name: str, pk_column: str, schema_name: Optional[str] = None) -> Dict[str, Any]:
        """Verify whether a column or business key is strictly unique with no duplicate rows."""
        return duckdb_inspector.check_primary_key_uniqueness(table_name, pk_column, schema=schema_name)

    # 6. Evaluation & Evidence Tools
    def validate_and_evaluate_model(
        model_name: str,
        layer: str = "trusted",
        primary_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run full evaluation suite on a model: compilation, build, data tests, guidelines, and DB evidence."""
        # Read current files from disk
        details = discovery.get_model_details(model_name)
        sql_content = details.raw_code if details else None
        report = evaluator.evaluate_model(
            model_name=model_name,
            layer=layer,
            sql_content=sql_content,
            primary_key=primary_key,
        )
        if session_id:
            session = session_store.get_session(session_id)
            if session:
                session.validation_history.append(report)
                if not report.passed:
                    session.outstanding_errors = [f.get("message", "Error") for f in report.dbt_failures]
                else:
                    session.outstanding_errors = []
                session_store.save_session(session)
        return report.model_dump()

    # Register each tool
    registry.register("discover_project", "Discover overall dbt project architecture and entities", discover_project)
    registry.register("list_models", "List models filtered optionally by layer", list_models)
    registry.register("get_model_details", "Get model columns, description, tests, and SQL", get_model_details)
    registry.register("get_model_lineage", "Get upstream and downstream dependencies of a model", get_model_lineage)
    registry.register("get_entity_definitions", "Discover existing ECM entity definitions", get_entity_definitions)
    registry.register("get_guidelines", "Read full Entity-Centric Data Modeling guidelines", get_guidelines)
    registry.register("check_guidelines_compliance", "Deterministic guideline policy check on SQL/YAML", check_guidelines_compliance)
    registry.register("read_model_file", "Read model SQL or YAML from models/ directory", read_model_file)
    registry.register("propose_model_diff", "Inspect unified diff of proposed changes", propose_model_diff)
    registry.register("write_model_file", "Safely create or update a model file in models/", write_model_file)
    registry.register("delete_model_file", "Safely delete a specific file in models/", delete_model_file)
    registry.register("delete_model", "Delete a model and its related SQL/YAML files from the project", delete_model)
    registry.register("revert_model_file", "Revert last change made to a model file", revert_model_file)
    registry.register("execute_dbt", "Execute controlled dbt command (compile, run, test, build)", execute_dbt)
    registry.register("query_database", "Execute read-only analytical SQL query on DuckDB", query_database)
    registry.register("inspect_table_profile", "Inspect table profile, null rates, and sample rows", inspect_table_profile)
    registry.register("check_pk_uniqueness", "Check primary key uniqueness on a table", check_pk_uniqueness)
    registry.register("validate_and_evaluate_model", "Full evaluation suite with evidence and report", validate_and_evaluate_model)

    services = {
        "config": cfg,
        "discovery": discovery,
        "guidelines": guidelines,
        "workspace": workspace,
        "dbt_runner": dbt_runner,
        "duckdb_inspector": duckdb_inspector,
        "evaluator": evaluator,
        "session_store": session_store,
    }

    return registry, services
