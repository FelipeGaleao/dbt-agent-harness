"""Tests for PRFormatter body generation."""

import pytest
from harness.core.contracts import ValidationReport
from harness.services.pr_formatter import PRFormatter


def test_pr_formatter_output():
    v_rep = ValidationReport(
        model_name="dim_aeroportos",
        passed=True,
        compilation_passed=True,
        build_passed=True,
        tests_passed=True,
        guidelines_passed=True,
    )

    models_meta = [
        {
            "model_name": "dim_aeroportos",
            "layer": "trusted",
            "materialized": "table",
            "grain": "1 linha por aeroporto",
            "primary_key": "codigo_oaci",
            "tests": ["unique", "not_null"],
        }
    ]

    profiling = {
        "trusted.dim_aeroportos": {
            "row_count": 496,
            "primary_key": "codigo_oaci",
            "is_unique": True,
            "null_rates": {"codigo_oaci": 0.0, "nm_municipio": 1.2},
            "preview_columns": ["codigo_oaci", "nome"],
            "preview_sample_rows": [["SBAA", "CONCEICAO"]],
        }
    }

    body = PRFormatter.build_pr_body(
        demand="Criar dimensão de aeroportos",
        target_models=models_meta,
        validation_reports=[v_rep],
        profiling_data=profiling,
    )

    assert "## 📋 Demanda Solicitada" in body
    assert "Criar dimensão de aeroportos" in body
    assert "## 🧪 Testes do dbt" in body
    assert "Todos os testes do dbt passaram com sucesso" in body
    assert "## 📊 Tabelas Geradas" in body
    assert "| `dim_aeroportos` | `trusted` | `table` |" in body
    assert "## 🔍 Profiling dos Dados" in body
    assert "`496` registros" in body
    assert "100% Única (0 duplicatas)" in body
