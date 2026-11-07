"""Configuration loader for the Agentic dbt Harness."""

from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel, Field


class HarnessConfig(BaseModel):
    project_root: Path = Field(default_factory=lambda: Path(os.getcwd()).resolve())
    dbt_project_dir: Path = Field(default_factory=lambda: Path(os.getcwd()).resolve() / "anac_lakehouse")
    database_path: Path = Field(default_factory=lambda: Path(os.getcwd()).resolve() / "databases" / "anac_lakehouse.db")
    guidelines_dir: Path = Field(default_factory=lambda: Path(os.getcwd()).resolve() / "guidelines")
    session_db_path: Path = Field(default_factory=lambda: Path(os.getcwd()).resolve() / ".harness" / "sessions.db")
    dbt_target_dir: Path = Field(default_factory=lambda: Path(os.getcwd()).resolve() / "anac_lakehouse" / "target")
    python_bin: Path = Field(default_factory=lambda: Path(os.getcwd()).resolve() / ".venv" / "bin" / "python")
    dbt_bin: Path = Field(default_factory=lambda: Path(os.getcwd()).resolve() / ".venv" / "bin" / "dbt")

    def ensure_directories(self) -> None:
        self.session_db_path.parent.mkdir(parents=True, exist_ok=True)


_DEFAULT_CONFIG: HarnessConfig | None = None


def get_config(project_root: str | Path | None = None) -> HarnessConfig:
    global _DEFAULT_CONFIG
    if project_root is not None:
        root = Path(project_root).resolve()
        return HarnessConfig(
            project_root=root,
            dbt_project_dir=root / "anac_lakehouse",
            database_path=root / "databases" / "anac_lakehouse.db",
            guidelines_dir=root / "guidelines",
            session_db_path=root / ".harness" / "sessions.db",
            dbt_target_dir=root / "anac_lakehouse" / "target",
            python_bin=root / ".venv" / "bin" / "python",
            dbt_bin=root / ".venv" / "bin" / "dbt",
        )
    if _DEFAULT_CONFIG is None:
        _DEFAULT_CONFIG = HarnessConfig()
    return _DEFAULT_CONFIG

