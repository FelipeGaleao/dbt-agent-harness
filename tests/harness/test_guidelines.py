"""Tests for guidelines and modeling policy service."""

import pytest
from harness.services.guidelines import GuidelinesService


@pytest.fixture
def guidelines_service():
    return GuidelinesService()


def test_get_raw_guidelines(guidelines_service):
    text = guidelines_service.get_raw_guidelines()
    assert "Entity-Centric Data Modeling" in text
    assert "dim_" in text


def test_get_rules(guidelines_service):
    rules = guidelines_service.get_rules()
    assert len(rules) >= 5
    rule_ids = [r.id for r in rules]
    assert "ECM-001" in rule_ids
    assert "ECM-003" in rule_ids


def test_validate_trusted_model_naming_success(guidelines_service):
    results = guidelines_service.validate_model_compliance(
        model_name="dim_customers",
        sql_content="select 1",
        layer="trusted",
    )
    rule_1 = next((r for r in results if r.rule_id == "ECM-001"), None)
    assert rule_1 is not None
    assert rule_1.passed is True


def test_validate_trusted_model_naming_violation(guidelines_service):
    results = guidelines_service.validate_model_compliance(
        model_name="customers_table",
        sql_content="select 1",
        layer="trusted",
    )
    rule_1 = next((r for r in results if r.rule_id == "ECM-001"), None)
    assert rule_1 is not None
    assert rule_1.passed is False
    assert rule_1.severity == "error"


def test_validate_trusted_reading_from_trusted_fails(guidelines_service):
    sql_bad = """
    select * from {{ ref('dim_aeronaves') }}
    """
    results = guidelines_service.validate_model_compliance(
        model_name="dim_proprietarios",
        sql_content=sql_bad,
        layer="trusted",
    )
    rule_8 = next((r for r in results if r.rule_id == "ECM-008"), None)
    assert rule_8 is not None
    assert rule_8.passed is False
    assert rule_8.severity == "error"


def test_validate_trusted_reading_from_staging_passes(guidelines_service):
    sql_good = """
    select * from {{ ref('stg_anac__rab_aeronaves') }}
    """
    results = guidelines_service.validate_model_compliance(
        model_name="dim_proprietarios",
        sql_content=sql_good,
        layer="trusted",
    )
    rule_8 = next((r for r in results if r.rule_id == "ECM-008"), None)
    assert rule_8 is not None
    assert rule_8.passed is True
    yaml_content = """
version: 2
models:
  - name: dim_orders
    description: "Wide table representing orders with grain 1 row per order"
    columns:
      - name: order_id
        tests:
          - unique
          - not_null
      - name: is_completed
        tests:
          - not_null
          - accepted_values:
              values: [true, false]
    """
    results = guidelines_service.validate_model_compliance(
        model_name="dim_orders",
        sql_content="select order_id, is_completed from orders",
        yaml_content=yaml_content,
        layer="trusted",
    )
    pk_check = next((r for r in results if r.rule_id == "ECM-003"), None)
    assert pk_check is not None
    assert pk_check.passed is True

    bool_check = next((r for r in results if "is_completed" in r.rule_title), None)
    assert bool_check is not None
    assert bool_check.passed is True


def test_validate_reports_reading_from_trusted_passes(guidelines_service):
    sql_good = """
    select * from {{ ref('dim_aeronaves') }}
    """
    results = guidelines_service.validate_model_compliance(
        model_name="rep_aeronaves_ativas",
        sql_content=sql_good,
        layer="reports",
    )
    rule_9 = next((r for r in results if r.rule_id == "ECM-009"), None)
    assert rule_9 is not None
    assert rule_9.passed is True


def test_validate_reports_reading_from_staging_fails(guidelines_service):
    sql_bad = """
    select * from {{ ref('stg_anac__rab_aeronaves') }}
    """
    results = guidelines_service.validate_model_compliance(
        model_name="rep_aeronaves_ativas",
        sql_content=sql_bad,
        layer="reports",
    )
    rule_9 = next((r for r in results if r.rule_id == "ECM-009"), None)
    assert rule_9 is not None
    assert rule_9.passed is False
    assert rule_9.severity == "error"

