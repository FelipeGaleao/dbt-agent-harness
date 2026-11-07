"""End-to-end integration test demonstrating discovery, modification, validation, and multi-turn session."""

import pytest
from harness.core.contracts import SessionStatus
from harness.services.factory import build_harness_tool_registry


def test_end_to_end_agentic_workflow(mocker):
    session_id = "e2e-session-001"
    registry, services = build_harness_tool_registry(session_id=session_id)
    session_store = services["session_store"]

    # 1. Initialize multi-turn session
    session = session_store.create_session(
        session_id=session_id,
        objective="Analyze models and extend trusted layer with dim_operators",
        requirements=["One row per operator", "Primary key operator_id", "Boolean is_active flag"],
    )
    assert session.status == SessionStatus.INITIALIZED

    # 2. Agent step: Project Discovery
    overview = registry.execute("discover_project")
    assert overview["project_name"] == "anac_lakehouse"
    assert "trusted" in overview["layers"]

    models = registry.execute("list_models", layer="trusted")
    assert any(m["name"] == "dim_aeronaves" for m in models)

    # 3. Agent step: Read guidelines before creating model
    guidelines_text = registry.execute("get_guidelines")
    assert "dim_" in guidelines_text
    assert "Grain" in guidelines_text

    # 4. Agent step: Propose and check guidelines on draft SQL/YAML
    proposed_sql = """
    select
        id as operator_id,
        nm_operador as nome_operador,
        coalesce(is_ativo, false) as is_ativo
    from {{ ref('stg_anac__rab_aeronaves') }}
    """
    proposed_yaml = """
    version: 2
    models:
      - name: dim_operators
        description: "Wide table representing aircraft operators with grain 1 row per operator"
        columns:
          - name: operator_id
            tests:
              - unique
              - not_null
          - name: is_ativo
            tests:
              - not_null
              - accepted_values:
                  values: [true, false]
    """

    compliance = registry.execute(
        "check_guidelines_compliance",
        model_name="dim_operators",
        sql_content=proposed_sql,
        yaml_content=proposed_yaml,
        layer="trusted",
    )
    assert all(c["passed"] for c in compliance if c["severity"] == "error")

    # 5. Agent step: Preview diff and write file safely
    diff = registry.execute(
        "propose_model_diff",
        relative_path="trusted/dim_operators.sql",
        new_content=proposed_sql,
    )
    assert "+        id as operator_id," in diff

    write_res = registry.execute(
        "write_model_file",
        relative_path="trusted/dim_operators.sql",
        content=proposed_sql,
    )
    assert write_res["action"] == "create"

    # Verify session tracking updated
    updated_session = session_store.get_session(session_id)
    assert "trusted/dim_operators.sql" in updated_session.modified_models
    assert updated_session.current_revision == 2

    # 6. Agent step: Mock compile/build/validation to evaluate without mutating main lakehouse state
    mocker.patch.object(
        services["dbt_runner"],
        "execute",
        return_value=mocker.MagicMock(
            success=True,
            failures=[],
            stderr="",
            stdout="",
            error_type=None,
        ),
    )
    mocker.patch.object(
        services["duckdb_inspector"],
        "get_row_count",
        return_value=150,
    )
    mocker.patch.object(
        services["duckdb_inspector"],
        "check_primary_key_uniqueness",
        return_value={"is_unique": True, "duplicate_samples": []},
    )
    mocker.patch.object(
        services["duckdb_inspector"],
        "preview_table",
        return_value=mocker.MagicMock(
            columns=["operator_id", "nome_operador", "is_ativo"],
            rows=[["OP1", "Aero Corp", True]],
            total_rows_sampled=1,
        ),
    )

    val_report = registry.execute(
        "validate_and_evaluate_model",
        model_name="dim_operators",
        layer="trusted",
        primary_key="operator_id",
    )
    assert val_report["passed"] is True
    assert val_report["compilation_passed"] is True
    assert val_report["build_passed"] is True
    assert val_report["evidence"]["row_count"] == 150

    # 7. Multi-turn step: Revert change and confirm clean state
    revert_ok = registry.execute("revert_model_file", relative_path="trusted/dim_operators.sql")
    assert revert_ok is True

    # 8. Complete session
    current_sess = session_store.get_session(session_id)
    current_sess.status = SessionStatus.COMPLETED
    session_store.save_session(current_sess)

    final_session = session_store.get_session(session_id)
    assert final_session.status == SessionStatus.COMPLETED
    assert len(final_session.validation_history) == 1
