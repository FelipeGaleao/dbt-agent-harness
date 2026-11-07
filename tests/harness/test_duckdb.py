"""Tests for DuckDBInspector read-only queries and safety guards."""

import pytest
from harness.core.config import get_config
from harness.services.duckdb_inspector import DuckDBInspector


@pytest.fixture
def duckdb_inspector():
    return DuckDBInspector(get_config())


def test_forbid_destructive_queries(duckdb_inspector):
    with pytest.raises(PermissionError) as exc1:
        duckdb_inspector.execute_query("DROP TABLE trusted.dim_aeronaves;")
    assert "Only read-only queries" in str(exc1.value)

    with pytest.raises(PermissionError) as exc2:
        duckdb_inspector.execute_query("DELETE FROM trusted.dim_aeronaves WHERE 1=1;")
    assert "Only read-only queries" in str(exc2.value)

    with pytest.raises(PermissionError) as exc3:
        duckdb_inspector.execute_query("SELECT 1; INSERT INTO my_table VALUES(1);")
    assert "restricted keyword" in str(exc3.value)


def test_list_schemas_and_tables(duckdb_inspector):
    schemas = duckdb_inspector.list_schemas()
    assert "trusted" in schemas
    assert "staging" in schemas

    tables = duckdb_inspector.list_tables(schema="trusted")
    table_names = [t["table"] for t in tables]
    assert "dim_aeronaves" in table_names


def test_check_pk_uniqueness(duckdb_inspector):
    res = duckdb_inspector.check_primary_key_uniqueness("dim_aeronaves", "marca_aeronave", schema="trusted")
    assert res["is_unique"] is True
    assert len(res["duplicate_samples"]) == 0


def test_row_count_and_preview(duckdb_inspector):
    count = duckdb_inspector.get_row_count("dim_aeronaves", schema="trusted")
    assert count > 0

    preview = duckdb_inspector.preview_table("dim_aeronaves", schema="trusted", limit=2)
    assert len(preview.rows) == 2
    assert "marca_aeronave" in preview.columns

