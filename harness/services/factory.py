"""Harness Services Factory and Default Tool Registry setup."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from harness.core.config import HarnessConfig, get_config
from harness.core.contracts import ValidationReport
from harness.core.registry import ToolRegistry
from harness.evals.evaluators import DeterministicEvaluator
from harness.evals.reports import ValidationReporter
from harness.services.dbt_runner import DbtRunner
from harness.services.discovery import DiscoveryService
from harness.services.duckdb_inspector import DuckDBInspector
from harness.services.git_service import GitService
from harness.services.guidelines import GuidelinesService
from harness.services.planning import ModelPlanItem, ModelingPlan, PlanStatus
from harness.services.pr_formatter import PRFormatter
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
    git_service = GitService(cfg)

    # In-memory session tracking for active plan & worktree
    active_plan: Optional[ModelingPlan] = None
    active_worktree_path: Optional[str] = None
    active_branch_name: Optional[str] = None

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

    # 7. Modeling Plan Tools
    def create_modeling_plan(
        demand: str,
        target_models: List[Dict[str, Any]],
        proposed_branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates and presents an interactive Modeling Plan in Markdown for user validation.
        The agent must present this plan and wait for user approval before writing code.
        """
        nonlocal active_plan, active_branch_name
        p_id = f"plan-{session_id or 'default'}"
        branch = proposed_branch or f"feature/{demand.lower().replace(' ', '-')[:25]}"

        plan_items = [
            ModelPlanItem(
                model_name=m.get("model_name", ""),
                layer=m.get("layer", "trusted"),
                materialized=m.get("materialized", "table"),
                description=m.get("description", ""),
                grain=m.get("grain", "1 linha por entidade"),
                primary_key=m.get("primary_key", "id"),
                upstream_sources=m.get("upstream_sources", []),
                columns=m.get("columns", {}),
                tests=m.get("tests", ["unique", "not_null"]),
            )
            for m in target_models
        ]

        active_plan = ModelingPlan(
            plan_id=p_id,
            session_id=session_id or "default",
            demand=demand,
            status=PlanStatus.AWAITING_APPROVAL,
            target_models=plan_items,
            proposed_branch=branch,
        )
        active_branch_name = branch

        if session_id:
            sess = session_store.get_session(session_id)
            if sess:
                sess.requirements = [f"Plan: {active_plan.plan_id} (Awaiting approval)"]
                sess.target_entities = [m.model_name for m in plan_items]
                session_store.save_session(sess)

        return {
            "plan_id": active_plan.plan_id,
            "status": active_plan.status.value,
            "proposed_branch": active_plan.proposed_branch,
            "markdown_presentation": active_plan.to_markdown(),
        }

    def approve_modeling_plan(plan_id: str) -> Dict[str, Any]:
        """
        Records user approval of the modeling plan and enables worktree creation.
        """
        nonlocal active_plan
        if not active_plan or active_plan.plan_id != plan_id:
            return {"error": f"No active plan matching '{plan_id}' found."}

        active_plan.status = PlanStatus.APPROVED
        if session_id:
            sess = session_store.get_session(session_id)
            if sess:
                sess.decisions_and_feedback.append(f"Plan {plan_id} approved by user.")
                session_store.save_session(sess)

        return {
            "plan_id": active_plan.plan_id,
            "status": "approved",
            "message": "Plano aprovado pelo usuário. Agora você pode chamar 'create_isolated_worktree'.",
        }

    # 8. Git Worktree & Pull Request Tools
    def create_isolated_worktree(branch_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates an isolated Git worktree on a feature branch for safe model development.
        Directs workspace edits to this worktree.
        """
        nonlocal active_worktree_path, active_branch_name
        b_name = branch_name or active_branch_name or f"feature/{session_id or 'dbt-dev'}"
        s_id = session_id or "default-session"

        try:
            wt_path = git_service.create_feature_worktree(session_id=s_id, branch_name=b_name)
            active_worktree_path = str(wt_path)
            active_branch_name = b_name

            # Point workspace to worktree's models folder
            models_in_worktree = wt_path / "anac_lakehouse" / "models"
            workspace.set_base_dir(models_in_worktree)

            return {
                "success": True,
                "worktree_path": str(wt_path),
                "branch_name": b_name,
                "message": f"Worktree isolada criada com sucesso na branch '{b_name}'.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def commit_changes_to_worktree(message: str) -> Dict[str, Any]:
        """
        Stages and commits all modifications inside the active worktree.
        """
        if not active_worktree_path:
            # Fallback to current project root
            try:
                res = git_service.commit_changes(Path(cfg.project_root), message)
                return {"success": True, "output": res}
            except Exception as e:
                return {"success": False, "error": str(e)}

        try:
            res = git_service.commit_changes(Path(active_worktree_path), message)
            return {"success": True, "output": res}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_pull_request(
        title: str,
        demand: Optional[str] = None,
        target_model_names: Optional[List[str]] = None,
        base_branch: str = "main",
    ) -> Dict[str, Any]:
        """
        Pushes branch to GitHub origin and opens a Pull Request with tests, markdown tables, and profiling.
        """
        nonlocal active_worktree_path, active_branch_name, active_plan
        branch = active_branch_name
        if not branch:
            # Detect current git branch
            import subprocess
            res_b = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=str(cfg.project_root))
            branch = res_b.stdout.strip() or "feature/model-update"

        wt_path = Path(active_worktree_path) if active_worktree_path else cfg.project_root

        # 1. Push branch
        try:
            git_service.push_branch(branch_name=branch, worktree_path=wt_path)
        except Exception as e:
            return {"success": False, "step": "git push", "error": str(e)}

        # 2. Collect profiling and validation reports
        models_to_report = target_model_names or []
        if active_plan and not models_to_report:
            models_to_report = [m.model_name for m in active_plan.target_models]

        plan_models_meta: List[Dict[str, Any]] = []
        val_reports: List[ValidationReport] = []
        profiling_dict: Dict[str, Dict[str, Any]] = []

        profiling_dict = {}
        for m_name in models_to_report:
            # Get validation report
            det = discovery.get_model_details(m_name)
            layer = det.layer if det else "trusted"
            v_rep = evaluator.evaluate_model(m_name, layer=layer)
            val_reports.append(v_rep)

            # Profile data
            schema_name = layer if layer in ("landing", "raw", "staging", "trusted") else "trusted"
            row_count = duckdb_inspector.get_row_count(m_name, schema=schema_name)
            pk = det.columns.keys() if det else []
            first_pk = next((k for k, col in det.columns.items() if "unique" in col.tests), "id") if det else "id"
            pk_check = duckdb_inspector.check_primary_key_uniqueness(m_name, first_pk, schema=schema_name)
            null_rates = duckdb_inspector.inspect_null_rates(m_name, schema=schema_name)
            preview = duckdb_inspector.preview_table(m_name, schema=schema_name, limit=3)

            profiling_dict[f"{schema_name}.{m_name}"] = {
                "row_count": row_count,
                "primary_key": first_pk,
                "is_unique": pk_check.get("is_unique", True),
                "null_rates": null_rates,
                "preview_columns": preview.columns,
                "preview_sample_rows": preview.rows,
            }

            plan_models_meta.append({
                "model_name": m_name,
                "layer": layer,
                "materialized": det.materialized if det else "table",
                "grain": f"1 linha por {m_name.replace('dim_', '')}",
                "primary_key": first_pk,
                "tests": ["unique", "not_null"],
            })

        # 3. Format PR Body
        pr_demand = demand or (active_plan.demand if active_plan else f"Implementação de {', '.join(models_to_report)}")
        pr_body = PRFormatter.build_pr_body(
            demand=pr_demand,
            target_models=plan_models_meta,
            validation_reports=val_reports,
            profiling_data=profiling_dict,
        )

        # 4. Open PR via gh CLI
        try:
            pr_result = git_service.create_pull_request(
                title=title,
                body=pr_body,
                branch_name=branch,
                base_branch=base_branch,
                worktree_path=wt_path,
            )

            # Clean up worktree if one was created
            if active_worktree_path:
                try:
                    git_service.cleanup_worktree(Path(active_worktree_path), force=True)
                    # Reset workspace path to root models
                    workspace.set_base_dir(cfg.dbt_project_dir / "models")
                except Exception:
                    pass

            return {
                "success": True,
                "pr_url": pr_result.get("url", ""),
                "status": pr_result.get("status", "created"),
                "branch": branch,
            }
        except Exception as e:
            return {"success": False, "step": "gh pr create", "error": str(e)}

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
    registry.register("create_modeling_plan", "Create and present an interactive Modeling Plan in Markdown", create_modeling_plan)
    registry.register("approve_modeling_plan", "Record user approval of a modeling plan", approve_modeling_plan)
    registry.register("create_isolated_worktree", "Create an isolated Git worktree on a feature branch", create_isolated_worktree)
    registry.register("commit_changes_to_worktree", "Stage and commit all changes in active worktree", commit_changes_to_worktree)
    registry.register("open_pull_request", "Push branch and open a GitHub PR with tests and profiling", open_pull_request)

    services = {
        "config": cfg,
        "discovery": discovery,
        "guidelines": guidelines,
        "workspace": workspace,
        "dbt_runner": dbt_runner,
        "duckdb_inspector": duckdb_inspector,
        "evaluator": evaluator,
        "session_store": session_store,
        "git_service": git_service,
    }

    return registry, services
