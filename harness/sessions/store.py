"""SQLite-backed multi-turn session persistence store."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from harness.core.config import HarnessConfig, get_config
from harness.core.contracts import SessionStatus, ValidationReport
from harness.sessions.models import SessionRecord


class SQLiteSessionStore:
    """Provides local durable session persistence independent of any agent framework."""

    def __init__(self, config: Optional[HarnessConfig] = None, db_path: Optional[Path] = None) -> None:
        self.config = config or get_config()
        self.db_path = db_path or self.config.session_db_path
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_revision INTEGER NOT NULL,
                    requirements TEXT NOT NULL,
                    target_entities TEXT NOT NULL,
                    modified_models TEXT NOT NULL,
                    validation_history TEXT NOT NULL,
                    outstanding_errors TEXT NOT NULL,
                    decisions_and_feedback TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def create_session(self, session_id: str, objective: str, requirements: Optional[List[str]] = None) -> SessionRecord:
        record = SessionRecord(
            session_id=session_id,
            objective=objective,
            requirements=requirements or [],
        )
        self.save_session(record)
        return record

    def save_session(self, session: SessionRecord) -> None:
        from datetime import datetime, timezone
        session.updated_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, objective, status, current_revision, requirements,
                    target_entities, modified_models, validation_history,
                    outstanding_errors, decisions_and_feedback, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    objective=excluded.objective,
                    status=excluded.status,
                    current_revision=excluded.current_revision,
                    requirements=excluded.requirements,
                    target_entities=excluded.target_entities,
                    modified_models=excluded.modified_models,
                    validation_history=excluded.validation_history,
                    outstanding_errors=excluded.outstanding_errors,
                    decisions_and_feedback=excluded.decisions_and_feedback,
                    updated_at=excluded.updated_at
                """,
                (
                    session.session_id,
                    session.objective,
                    session.status.value,
                    session.current_revision,
                    json.dumps(session.requirements),
                    json.dumps(session.target_entities),
                    json.dumps(session.modified_models),
                    json.dumps([v.model_dump() for v in session.validation_history]),
                    json.dumps(session.outstanding_errors),
                    json.dumps(session.decisions_and_feedback),
                    session.created_at,
                    session.updated_at,
                ),
            )
            conn.commit()

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT session_id, objective, status, current_revision, requirements,
                       target_entities, modified_models, validation_history,
                       outstanding_errors, decisions_and_feedback, created_at, updated_at
                FROM sessions WHERE session_id = ?
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return SessionRecord(
                session_id=row[0],
                objective=row[1],
                status=SessionStatus(row[2]),
                current_revision=row[3],
                requirements=json.loads(row[4]),
                target_entities=json.loads(row[5]),
                modified_models=json.loads(row[6]),
                validation_history=[ValidationReport(**v) for v in json.loads(row[7])],
                outstanding_errors=json.loads(row[8]),
                decisions_and_feedback=json.loads(row[9]),
                created_at=row[10],
                updated_at=row[11],
            )

    def list_sessions(self) -> List[SessionRecord]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT session_id, objective, status, current_revision, requirements,
                       target_entities, modified_models, validation_history,
                       outstanding_errors, decisions_and_feedback, created_at, updated_at
                FROM sessions ORDER BY updated_at DESC
                """
            )
            records: List[SessionRecord] = []
            for row in cursor.fetchall():
                records.append(
                    SessionRecord(
                        session_id=row[0],
                        objective=row[1],
                        status=SessionStatus(row[2]),
                        current_revision=row[3],
                        requirements=json.loads(row[4]),
                        target_entities=json.loads(row[5]),
                        modified_models=json.loads(row[6]),
                        validation_history=[ValidationReport(**v) for v in json.loads(row[7])],
                        outstanding_errors=json.loads(row[8]),
                        decisions_and_feedback=json.loads(row[9]),
                        created_at=row[10],
                        updated_at=row[11],
                    )
                )
            return records

    def delete_session(self, session_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0
