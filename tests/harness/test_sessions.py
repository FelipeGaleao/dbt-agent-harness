"""Tests for multi-turn session persistence with SQLite."""

import tempfile
from pathlib import Path
import pytest
from harness.core.contracts import SessionStatus, ValidationReport
from harness.sessions.models import SessionRecord
from harness.sessions.store import SQLiteSessionStore


@pytest.fixture
def session_store():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = SQLiteSessionStore(db_path=Path(tmp.name))
        yield store


def test_session_lifecycle(session_store):
    # 1. Create session
    session = session_store.create_session(
        session_id="sess-001",
        objective="Create trusted dim_customers",
        requirements=["1 row per customer", "unique customer_id"],
    )
    assert session.session_id == "sess-001"
    assert session.status == SessionStatus.INITIALIZED

    # 2. Retrieve session
    retrieved = session_store.get_session("sess-001")
    assert retrieved is not None
    assert retrieved.objective == "Create trusted dim_customers"
    assert len(retrieved.requirements) == 2

    # 3. Update session
    retrieved.status = SessionStatus.VALIDATING
    retrieved.modified_models.append("models/trusted/dim_customers.sql")
    retrieved.current_revision = 2
    session_store.save_session(retrieved)

    updated = session_store.get_session("sess-001")
    assert updated.status == SessionStatus.VALIDATING
    assert updated.current_revision == 2
    assert "models/trusted/dim_customers.sql" in updated.modified_models

    # 4. Record validation
    val_report = ValidationReport(
        model_name="dim_customers",
        passed=True,
        compilation_passed=True,
        build_passed=True,
        tests_passed=True,
        guidelines_passed=True,
    )
    updated.validation_history.append(val_report)
    session_store.save_session(updated)

    with_val = session_store.get_session("sess-001")
    assert len(with_val.validation_history) == 1
    assert with_val.validation_history[0].passed is True

    # 5. List and delete
    sessions = session_store.list_sessions()
    assert len(sessions) == 1
    deleted = session_store.delete_session("sess-001")
    assert deleted is True
    assert session_store.get_session("sess-001") is None

