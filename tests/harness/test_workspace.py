"""Tests for WorkspaceManager safe operations and boundaries."""

import pytest
from harness.core.config import get_config
from harness.services.workspace import WorkspaceManager


@pytest.fixture
def workspace_manager():
    return WorkspaceManager(get_config())


def test_path_boundary_enforcement(workspace_manager):
    # Attempting to read or write outside models/ must raise PermissionError
    with pytest.raises(PermissionError):
        workspace_manager.read_model_file("../dbt_project.yml")

    with pytest.raises(PermissionError):
        workspace_manager.write_model_file("../evil.txt", "payload")


def test_read_existing_model(workspace_manager):
    content = workspace_manager.read_model_file("trusted/dim_aeronaves.sql")
    assert "dim_aeronaves" in content
    assert "marca_aeronave" in content


def test_delete_model_file_and_rollback(workspace_manager):
    test_rel_path = "trusted/test_deletion_model.sql"
    workspace_manager.write_model_file(test_rel_path, "select 42 as answer;")
    assert workspace_manager.read_model_file(test_rel_path) == "select 42 as answer;"

    # Delete
    del_change = workspace_manager.delete_model_file(test_rel_path)
    assert del_change.action == "delete"
    with pytest.raises(FileNotFoundError):
        workspace_manager.read_model_file(test_rel_path)

    # Rollback delete
    reverted = workspace_manager.revert_file(test_rel_path)
    assert reverted is True
    assert workspace_manager.read_model_file(test_rel_path) == "select 42 as answer;"

    # Cleanup
    workspace_manager.delete_model_file(test_rel_path)


def test_delete_model_by_name(workspace_manager):
    sql_path = "trusted/temp_test_to_delete.sql"
    yml_path = "trusted/temp_test_to_delete.yml"
    workspace_manager.write_model_file(sql_path, "select 1 as x;")
    workspace_manager.write_model_file(yml_path, "version: 2\nmodels:\n  - name: temp_test_to_delete\n")

    changes = workspace_manager.delete_model("temp_test_to_delete", layer="trusted")
    deleted_paths = [c.path for c in changes]
    assert any("temp_test_to_delete.sql" in p for p in deleted_paths)
    assert any("temp_test_to_delete.yml" in p for p in deleted_paths)
    test_rel_path = "trusted/test_temporary_model.sql"
    initial_content = "select 1 as id;"

    # 1. Propose diff
    diff = workspace_manager.propose_diff(test_rel_path, initial_content)
    assert "+select 1 as id;" in diff

    # 2. Write file
    change = workspace_manager.write_model_file(test_rel_path, initial_content)
    assert change.action == "create"
    assert workspace_manager.read_model_file(test_rel_path) == initial_content

    # 3. Modify file
    updated_content = "select 2 as id;"
    change_mod = workspace_manager.write_model_file(test_rel_path, updated_content)
    assert change_mod.action == "modify"
    assert workspace_manager.read_model_file(test_rel_path) == updated_content

    # 4. Revert modification
    reverted = workspace_manager.revert_file(test_rel_path)
    assert reverted is True
    assert workspace_manager.read_model_file(test_rel_path) == initial_content

    # 5. Revert creation (deletes file)
    reverted_creation = workspace_manager.revert_file(test_rel_path)
    assert reverted_creation is True
    with pytest.raises(FileNotFoundError):
        workspace_manager.read_model_file(test_rel_path)

