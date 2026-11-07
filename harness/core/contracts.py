"""Pydantic contracts and data transfer objects for the Agentic dbt Harness."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Layer(str, Enum):
    LANDING = "landing"
    RAW = "raw"
    STAGING = "staging"
    TRUSTED = "trusted"
    CUSTOM = "custom"


class ColumnMetadata(BaseModel):
    name: str
    data_type: Optional[str] = None
    description: Optional[str] = None
    tests: List[str] = Field(default_factory=list)


class ModelMetadata(BaseModel):
    name: str
    unique_id: str
    layer: str
    relation_name: Optional[str] = None
    materialized: str = "table"
    path: str
    description: Optional[str] = None
    columns: Dict[str, ColumnMetadata] = Field(default_factory=dict)
    depends_on_nodes: List[str] = Field(default_factory=list)
    raw_code: Optional[str] = None
    compiled_code: Optional[str] = None


class LineageGraph(BaseModel):
    model_name: str
    upstream: List[str] = Field(default_factory=list)
    downstream: List[str] = Field(default_factory=list)


class EntityDefinition(BaseModel):
    entity_name: str
    model_name: str
    primary_key: Optional[str] = None
    description: Optional[str] = None
    features: List[str] = Field(default_factory=list)
    grain: Optional[str] = None


class ProjectOverview(BaseModel):
    project_name: str
    dbt_version: str
    total_models: int
    layers: Dict[str, List[str]] = Field(default_factory=dict)
    entities: List[str] = Field(default_factory=list)
    database_path: str


class GuidelineRule(BaseModel):
    id: str
    title: str
    category: str
    description: str
    severity: str = "error"  # "error" or "warning"


class ComplianceCheckResult(BaseModel):
    rule_id: str
    rule_title: str
    passed: bool
    details: str
    severity: str = "error"


class WorkspaceFileChange(BaseModel):
    path: str
    action: str  # "create", "modify", "delete"
    diff: Optional[str] = None
    previous_content: Optional[str] = None


class DbtExecutionResult(BaseModel):
    command: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    models_affected: List[str] = Field(default_factory=list)
    failures: List[Dict[str, Any]] = Field(default_factory=list)
    error_type: Optional[str] = None  # "compilation", "runtime", "data_test", "lock_error", "timeout"


class TablePreview(BaseModel):
    schema_name: str
    table_name: str
    columns: List[str]
    rows: List[List[Any]]
    total_rows_sampled: int


class QueryResult(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    execution_time_seconds: float


class ValidationReport(BaseModel):
    model_name: str
    passed: bool
    compilation_passed: bool
    build_passed: bool
    tests_passed: bool
    guidelines_passed: bool
    compliance_checks: List[ComplianceCheckResult] = Field(default_factory=list)
    dbt_failures: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    remaining_uncertainties: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SessionStatus(str, Enum):
    INITIALIZED = "initialized"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    COMPLETED = "completed"
    REVERTED = "reverted"
