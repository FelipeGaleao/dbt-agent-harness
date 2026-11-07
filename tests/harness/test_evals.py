"""Tests for DeterministicEvaluator and ValidationReporter."""

import pytest
from harness.core.contracts import ComplianceCheckResult, ValidationReport
from harness.evals.evaluators import DeterministicEvaluator
from harness.evals.reports import ValidationReporter
from harness.services.dbt_runner import DbtRunner
from harness.services.duckdb_inspector import DuckDBInspector
from harness.services.guidelines import GuidelinesService
from harness.services.workspace import WorkspaceManager


def test_validation_reporter_format():
    report = ValidationReport(
        model_name="dim_aeronaves",
        passed=True,
        compilation_passed=True,
        build_passed=True,
        tests_passed=True,
        guidelines_passed=True,
        compliance_checks=[
            ComplianceCheckResult(
                rule_id="ECM-001",
                rule_title="Trusted Naming",
                passed=True,
                details="Starts with dim_",
            )
        ],
        evidence={"row_count": 35027},
    )

    md = ValidationReporter.format_markdown(report)
    assert "# Validation Report: `dim_aeronaves` (✅ PASSED)" in md
    assert "row_count" in md
    assert "ECM-001" in md


def test_evaluator_with_mocked_runner(mocker):
    mock_runner = mocker.MagicMock(spec=DbtRunner)
    mock_runner.execute.return_value = mocker.MagicMock(success=True, failures=[])

    mock_duckdb = mocker.MagicMock(spec=DuckDBInspector)
    mock_duckdb.get_row_count.return_value = 100
    mock_duckdb.check_primary_key_uniqueness.return_value = {"is_unique": True, "duplicate_samples": []}
    mock_duckdb.preview_table.return_value = mocker.MagicMock(columns=["id"], rows=[[1]], total_rows_sampled=1)

    evaluator = DeterministicEvaluator(
        dbt_runner=mock_runner,
        duckdb_inspector=mock_duckdb,
        guidelines_service=GuidelinesService(),
        workspace_manager=mocker.MagicMock(spec=WorkspaceManager),
    )

    report = evaluator.evaluate_model(
        model_name="dim_test",
        layer="trusted",
        sql_content="select 1 as id",
        primary_key="id",
    )
    assert report.passed is True
    assert report.evidence["row_count"] == 100
    assert report.evidence["pk_uniqueness"]["is_unique"] is True

