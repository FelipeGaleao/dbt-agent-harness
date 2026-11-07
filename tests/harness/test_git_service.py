"""Tests for GitService worktree, commit, and PR creation."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from harness.services.git_service import GitService


@pytest.fixture
def git_service():
    return GitService()


def test_worktree_lifecycle_with_mocks(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="Success", stderr=""))
    mock_config = MagicMock()
    mock_config.project_root = tmp_path
    service = GitService(config=mock_config)

    wt_path = service.create_feature_worktree(session_id="sess-123", branch_name="feature/my-branch")
    assert wt_path.name == "sess-123"


def test_commit_changes(mocker, git_service, tmp_path):
    mock_run = mocker.patch("subprocess.run")
    # First call: git status --porcelain
    # Second call: git add .
    # Third call: git commit -m ...
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="M  model.sql"),
        MagicMock(returncode=0, stdout=""),
        MagicMock(returncode=0, stdout="[feature/test abc1234] feat: add model"),
    ]

    out = git_service.commit_changes(tmp_path, "feat: add model")
    assert "feat: add model" in out


def test_factory_commit_tool_uses_path(mocker):
    from harness.services.factory import build_harness_tool_registry
    registry, _ = build_harness_tool_registry()
    tool = registry.get("commit_changes_to_worktree")
    assert tool is not None
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="clean", stderr=""))
    # Should not raise NameError: name 'Path' is not defined
    res = tool.handler(message="test commit")
    assert "success" in res


def test_create_pull_request(mocker, git_service, tmp_path):
    mock_run = mocker.patch("subprocess.run")
    # Check if exists (fails with 1, so creates) -> gh pr create returns url
    mock_run.side_effect = [
        MagicMock(returncode=1, stdout="", stderr="no pull requests found"),
        MagicMock(returncode=0, stdout="https://github.com/org/repo/pull/42\n", stderr=""),
    ]

    res = git_service.create_pull_request(
        title="feat: add customer entity",
        body="## Demanda\nTest",
        branch_name="feature/customer-entity",
        worktree_path=tmp_path,
    )
    assert res["status"] == "created"
    assert "https://github.com/org/repo/pull/42" in res["url"]
