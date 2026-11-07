from pathlib import Path
from unittest.mock import MagicMock
from harness.services.dbt_runner import DbtRunner
from harness.services.discovery import DiscoveryService
from harness.services.factory import build_harness_tool_registry

def test_runner_and_discovery_switch_to_worktree(tmp_path):
    runner = DbtRunner()
    discovery = DiscoveryService()
    
    assert "anac_lakehouse" in str(runner.current_project_dir)
    assert "anac_lakehouse" in str(discovery.current_project_dir)
    
    # Switch to isolated worktree
    wt_dir = tmp_path / "worktree_session" / "anac_lakehouse"
    runner.set_project_dir(wt_dir)
    discovery.set_project_dir(wt_dir)
    
    assert runner.current_project_dir == wt_dir
    assert discovery.current_project_dir == wt_dir
    assert runner.current_target_dir == wt_dir / "target"
    assert discovery.current_target_dir == wt_dir / "target"

def test_query_database_returns_helpful_suggestion_on_catalog_error(mocker):
    registry, _ = build_harness_tool_registry()
    query_tool = registry.get("query_database")
    
    # Simulate CatalogException / Table does not exist
    import duckdb
    mocker.patch(
        "harness.services.duckdb_inspector.DuckDBInspector.execute_query",
        side_effect=duckdb.CatalogException("Table with name rpt_test does not exist!")
    )
    
    res = query_tool.handler("SELECT * FROM reports.rpt_test")
    assert "error" in res
    assert "não foi encontrada" in res.get("suggestion", "")
