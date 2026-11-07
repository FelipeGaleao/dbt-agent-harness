"""Deterministic evaluator for dbt models and validation reports."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from harness.core.config import HarnessConfig, get_config
from harness.core.contracts import ValidationReport
from harness.services.dbt_runner import DbtRunner
from harness.services.duckdb_inspector import DuckDBInspector
from harness.services.guidelines import GuidelinesService
from harness.services.workspace import WorkspaceManager


class DeterministicEvaluator:
    """Evaluates dbt models across SQL compilation, dbt build, data tests, guidelines, and DuckDB evidence."""

    def __init__(
        self,
        config: Optional[HarnessConfig] = None,
        dbt_runner: Optional[DbtRunner] = None,
        guidelines_service: Optional[GuidelinesService] = None,
        duckdb_inspector: Optional[DuckDBInspector] = None,
        workspace_manager: Optional[WorkspaceManager] = None,
    ) -> None:
        self.config = config or get_config()
        self.dbt_runner = dbt_runner or DbtRunner(self.config)
        self.guidelines_service = guidelines_service or GuidelinesService(self.config)
        self.duckdb_inspector = duckdb_inspector or DuckDBInspector(self.config)
        self.workspace_manager = workspace_manager or WorkspaceManager(self.config)

    def evaluate_model(
        self,
        model_name: str,
        layer: str = "trusted",
        sql_content: Optional[str] = None,
        yaml_content: Optional[str] = None,
        primary_key: Optional[str] = None,
    ) -> ValidationReport:
        evidence: Dict[str, Any] = {}
        warnings: List[str] = []
        uncertainties: List[str] = []
        dbt_failures: List[Dict[str, Any]] = []

        # 1. Guideline & Policy checks
        compliance_checks = []
        if sql_content:
            compliance_checks = self.guidelines_service.validate_model_compliance(
                model_name=model_name,
                sql_content=sql_content,
                yaml_content=yaml_content,
                layer=layer,
            )
        guidelines_passed = not any(c.severity == "error" and not c.passed for c in compliance_checks)

        # 2. dbt compile check
        compile_res = self.dbt_runner.execute("compile", select=model_name)
        compilation_passed = compile_res.success
        if not compilation_passed:
            dbt_failures.extend(compile_res.failures or [{"message": compile_res.stderr or compile_res.stdout}])
            if compile_res.error_type == "lock_error":
                uncertainties.append("DuckDB database file locked by external process during dbt compile.")

        # 3. dbt build / test check
        build_passed = False
        tests_passed = False
        if compilation_passed:
            build_res = self.dbt_runner.execute("build", select=model_name)
            build_passed = build_res.success
            if not build_passed:
                dbt_failures.extend(build_res.failures or [{"message": build_res.stderr or build_res.stdout}])
                if build_res.error_type == "lock_error":
                    uncertainties.append("DuckDB database file locked by external process during dbt build.")
                elif build_res.error_type == "data_test":
                    uncertainties.append("One or more dbt tests failed during build.")
            else:
                tests_passed = True
        else:
            uncertainties.append("Build skipped due to compilation failure.")

        # 4. DuckDB Evidence collection (Read-Only)
        try:
            target_table = model_name
            schema = layer if layer in ("landing", "raw", "staging", "trusted") else "trusted"
            # Get row count
            row_count = self.duckdb_inspector.get_row_count(target_table, schema=schema)
            evidence["row_count"] = row_count

            # Check primary key if provided
            if primary_key:
                pk_check = self.duckdb_inspector.check_primary_key_uniqueness(target_table, primary_key, schema=schema)
                evidence["pk_uniqueness"] = pk_check
                if not pk_check["is_unique"]:
                    warnings.append(f"Duplicate primary keys detected in {schema}.{target_table} on column '{primary_key}'")

            # Check preview
            preview = self.duckdb_inspector.preview_table(target_table, schema=schema, limit=3)
            evidence["sample_columns"] = preview.columns
            evidence["sample_rows_count"] = preview.total_rows_sampled
        except Exception as e:
            evidence["duckdb_inspection_error"] = str(e)
            uncertainties.append(f"DuckDB inspection could not inspect output: {e}")

        overall_passed = compilation_passed and build_passed and guidelines_passed and not any(f.get("status") == "fail" for f in dbt_failures)

        return ValidationReport(
            model_name=model_name,
            passed=overall_passed,
            compilation_passed=compilation_passed,
            build_passed=build_passed,
            tests_passed=tests_passed,
            guidelines_passed=guidelines_passed,
            compliance_checks=compliance_checks,
            dbt_failures=dbt_failures,
            evidence=evidence,
            warnings=warnings,
            remaining_uncertainties=uncertainties,
        )

