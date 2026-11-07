"""Models for persistent multi-turn sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from harness.core.contracts import SessionStatus, ValidationReport


class SessionModification(BaseModel):
    revision: int
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    file_path: str
    action: str  # create, modify, revert
    diff: Optional[str] = None


class SessionRecord(BaseModel):
    session_id: str
    objective: str
    status: SessionStatus = SessionStatus.INITIALIZED
    current_revision: int = 1
    requirements: List[str] = Field(default_factory=list)
    target_entities: List[str] = Field(default_factory=list)
    modified_models: List[str] = Field(default_factory=list)
    validation_history: List[ValidationReport] = Field(default_factory=list)
    outstanding_errors: List[str] = Field(default_factory=list)
    decisions_and_feedback: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
