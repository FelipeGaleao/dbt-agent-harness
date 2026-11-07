"""Tests for ModelingPlan creation and formatting."""

import pytest
from harness.services.planning import ModelPlanItem, ModelingPlan, PlanStatus


def test_modeling_plan_to_markdown():
    plan = ModelingPlan(
        plan_id="plan-001",
        session_id="sess-001",
        demand="Modelar aeroportos civis públicos",
        status=PlanStatus.AWAITING_APPROVAL,
        proposed_branch="feature/aeroportos",
        target_models=[
            ModelPlanItem(
                model_name="dim_aeroportos",
                layer="trusted",
                materialized="table",
                description="Visão analítica de aeródromos",
                grain="1 linha por aeródromo (codigo_oaci)",
                primary_key="codigo_oaci",
                upstream_sources=["stg_anac__aerodromos"],
                columns={"codigo_oaci": "Código OACI do aeródromo", "nm_aerodromo": "Nome oficial"},
                tests=["unique", "not_null"],
            )
        ],
    )

    md = plan.to_markdown()
    assert "# 📐 Plano de Modelagem dbt: `plan-001`" in md
    assert "Modelar aeroportos civis públicos" in md
    assert "dim_aeroportos" in md
    assert "stg_anac__aerodromos" in md
    assert "codigo_oaci" in md

