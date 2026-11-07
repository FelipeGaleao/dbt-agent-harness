"""Tests for Google ADK Runtime."""

import pytest
from unittest.mock import MagicMock
from harness.adapters.adk_runtime import ADKRuntime


def test_adk_runtime_initialization(tmp_path):
    runtime = ADKRuntime(session_id="test-adk-runtime-01")
    assert runtime.session_id == "test-adk-runtime-01"
    assert runtime.agent is not None
    assert runtime.runner is not None
    assert runtime.session_service is not None


def test_adk_runtime_send_message_stream(mocker):
    runtime = ADKRuntime(session_id="test-adk-runtime-02")

    # Mock runner.run to return sample events without requiring live API credentials
    mock_event1 = mocker.MagicMock()
    mock_event1.text = "Identifiquei 5 modelos no projeto anac_lakehouse."

    mock_event2 = mocker.MagicMock()
    mock_event2.text = " Modelo dim_aeronaves validado com sucesso."

    mocker.patch.object(runtime.runner, "run", return_value=[mock_event1, mock_event2])

    responses = list(runtime.send_message("Descubra os modelos do lakehouse"))
    assert len(responses) == 2
    assert "Identifiquei 5 modelos" in responses[0]
    assert "dim_aeronaves" in responses[1]

