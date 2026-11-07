"""Tests for DbtRunner execution and failure classification."""

import pytest
from unittest.mock import MagicMock
from harness.core.config import get_config
from harness.services.dbt_runner import DbtRunner


@pytest.fixture
def dbt_runner():
    return DbtRunner(get_config())


def test_command_whitelisting(dbt_runner):
    with pytest.raises(ValueError) as exc:
        dbt_runner.execute("drop-database")
    assert "not allowed" in str(exc.value)


def test_classify_lock_error():
    err_type = DbtRunner._classify_error(
        stdout="Error encountered",
        stderr='IO Error: Could not set lock on file "/path/db": Conflicting lock is held',
        exit_code=1,
        failures=[],
    )
    assert err_type == "lock_error"


def test_classify_compilation_error():
    err_type = DbtRunner._classify_error(
        stdout="Compilation Error in model x (models/x.sql)\nSyntax error at or near 'FORM'",
        stderr="",
        exit_code=1,
        failures=[],
    )
    assert err_type == "compilation"


def test_mocked_execution(mocker, dbt_runner):
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="Completed successfully",
        stderr="",
    )
    res = dbt_runner.execute("compile", select="dim_aeronaves")
    assert res.success is True
    assert res.exit_code == 0
    assert "compile" in res.command
    assert "--select dim_aeronaves" in res.command

