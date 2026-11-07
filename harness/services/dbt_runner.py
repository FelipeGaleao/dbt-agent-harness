"""dbt Execution Service with controlled subprocesses and structured failure reporting."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from harness.core.config import HarnessConfig, get_config
from harness.core.contracts import DbtExecutionResult


class DbtRunner:
    """Executes validated dbt commands via controlled subprocesses."""

    ALLOWED_COMMANDS = {"parse", "compile", "run", "test", "build", "seed"}

    def __init__(self, config: Optional[HarnessConfig] = None) -> None:
        self.config = config or get_config()
        self._custom_dbt_project_dir: Optional[Path] = None

    def set_project_dir(self, project_dir: Optional[Path]) -> None:
        """Sets an alternate working directory (e.g. for an active git worktree)."""
        self._custom_dbt_project_dir = Path(project_dir).resolve() if project_dir else None

    @property
    def current_project_dir(self) -> Path:
        return self._custom_dbt_project_dir or self.config.dbt_project_dir

    @property
    def current_target_dir(self) -> Path:
        return self.current_project_dir / "target"

    def execute(
        self,
        command: str,
        select: Optional[str] = None,
        models: Optional[List[str]] = None,
        vars_dict: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 60.0,
    ) -> DbtExecutionResult:
        """Executes a sanitized dbt command without arbitrary shell injection."""
        cmd_base = command.strip().lower()
        if cmd_base not in self.ALLOWED_COMMANDS:
            raise ValueError(
                f"Command '{command}' is not allowed. Allowed: {sorted(list(self.ALLOWED_COMMANDS))}"
            )

        cmd_args = [str(self.config.dbt_bin), cmd_base]

        # Handle selector
        selector = select
        if not selector and models:
            selector = " ".join(models)

        if selector:
            cmd_args.extend(["--select", selector])

        if vars_dict:
            cmd_args.extend(["--vars", json.dumps(vars_dict)])

        # Ensure profiles dir is set to current project dir
        cmd_args.extend(["--profiles-dir", str(self.current_project_dir)])

        start_time = time.time()
        try:
            env = os.environ.copy()
            # Ensure venv python is first on path
            env["PATH"] = f"{self.config.python_bin.parent}:{env.get('PATH', '')}"

            proc = subprocess.run(
                cmd_args,
                cwd=str(self.current_project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
                env=env,
            )
            duration = time.time() - start_time
            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode

            # Analyze failures and run_results.json
            failures, affected_models = self._parse_run_results()
            error_type = self._classify_error(stdout, stderr, exit_code, failures)

            return DbtExecutionResult(
                command=" ".join(cmd_args),
                success=(exit_code == 0),
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=round(duration, 3),
                models_affected=affected_models,
                failures=failures,
                error_type=error_type,
            )

        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            return DbtExecutionResult(
                command=" ".join(cmd_args),
                success=False,
                exit_code=-1,
                stdout=e.stdout or "",
                stderr=e.stderr or "Command timed out",
                duration_seconds=round(duration, 3),
                error_type="timeout",
                failures=[{"message": f"Execution timed out after {timeout_seconds} seconds."}],
            )
        except Exception as e:
            duration = time.time() - start_time
            return DbtExecutionResult(
                command=" ".join(cmd_args),
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=round(duration, 3),
                error_type="runtime",
                failures=[{"message": str(e)}],
            )

    def _parse_run_results(self) -> tuple[List[Dict[str, Any]], List[str]]:
        run_results_path = self.current_target_dir / "run_results.json"
        failures: List[Dict[str, Any]] = []
        affected_models: List[str] = []

        if not run_results_path.exists():
            return failures, affected_models

        try:
            with open(run_results_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for result in data.get("results", []):
                unique_id = result.get("unique_id", "")
                status = result.get("status", "")
                failures_count = result.get("failures")
                message = result.get("message", "")

                affected_models.append(unique_id)

                if status in ("error", "fail") or (failures_count and failures_count > 0):
                    failures.append(
                        {
                            "unique_id": unique_id,
                            "status": status,
                            "message": message,
                            "failures": failures_count,
                        }
                    )
        except Exception:
            pass

        return failures, affected_models

    @staticmethod
    def _classify_error(stdout: str, stderr: str, exit_code: int, failures: List[Dict[str, Any]]) -> Optional[str]:
        if exit_code == 0:
            return None
        combined = (stdout + " " + stderr).lower()
        if "could not set lock" in combined or "conflicting lock is held" in combined:
            return "lock_error"
        if "compilation error" in combined or "syntax error" in combined or "jinja2.exceptions" in combined:
            return "compilation"
        if any(f.get("status") == "fail" for f in failures):
            return "data_test"
        return "runtime"

