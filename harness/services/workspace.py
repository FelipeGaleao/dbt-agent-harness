"""Workspace and File Management Service for safe dbt modifications."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Dict, List, Optional

from harness.core.config import HarnessConfig, get_config
from harness.core.contracts import WorkspaceFileChange


class WorkspaceManager:
    """Safely manages model files with boundary enforcement, diff inspection, and reversions."""

    def __init__(self, config: Optional[HarnessConfig] = None, base_dir: Optional[Path] = None) -> None:
        self.config = config or get_config()
        self.allowed_base_dir = (base_dir or (self.config.dbt_project_dir / "models")).resolve()
        # Track history of file modifications in-memory or for session: {path: [previous_contents]}
        self._history: Dict[str, List[Optional[str]]] = {}

    def set_base_dir(self, base_dir: Path) -> None:
        """Dynamically re-points the workspace to an isolated worktree directory."""
        self.allowed_base_dir = base_dir.resolve()

    def _validate_path(self, relative_path: str) -> Path:
        """Ensures target path is strictly within the allowed models directory."""
        clean_rel = relative_path.strip().lstrip("/")
        if clean_rel.startswith("models/"):
            clean_rel = clean_rel[len("models/"):]
        target_path = (self.allowed_base_dir / clean_rel).resolve()
        try:
            target_path.relative_to(self.allowed_base_dir)
        except ValueError:
            raise PermissionError(
                f"Security violation: path '{relative_path}' is outside the allowed models directory '{self.allowed_base_dir}'."
            )
        return target_path

    def read_model_file(self, relative_path: str) -> str:
        """Reads a file within the allowed models directory."""
        target_path = self._validate_path(relative_path)
        if not target_path.exists():
            raise FileNotFoundError(f"Model file not found: {relative_path}")
        return target_path.read_text(encoding="utf-8")

    def propose_diff(self, relative_path: str, new_content: str) -> str:
        """Computes a unified diff between current file content and proposed content."""
        target_path = self._validate_path(relative_path)
        old_content = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
        )
        return "".join(diff)

    def write_model_file(self, relative_path: str, content: str) -> WorkspaceFileChange:
        """Creates or updates a model file inside models/, tracking previous content for rollback."""
        target_path = self._validate_path(relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        old_content: Optional[str] = None
        action = "create"
        if target_path.exists():
            action = "modify"
            old_content = target_path.read_text(encoding="utf-8")

        diff = self.propose_diff(relative_path, content)

        # Record history
        self._history.setdefault(str(target_path), []).append(old_content)

        target_path.write_text(content, encoding="utf-8")

        return WorkspaceFileChange(
            path=relative_path,
            action=action,
            diff=diff,
            previous_content=old_content,
        )

    def delete_model_file(self, relative_path: str) -> WorkspaceFileChange:
        """Safely deletes a model SQL or YAML file within models/, tracking previous content for rollback."""
        target_path = self._validate_path(relative_path)
        if not target_path.exists():
            raise FileNotFoundError(f"Model file not found: {relative_path}")

        old_content = target_path.read_text(encoding="utf-8")
        diff = self.propose_diff(relative_path, "")

        # Record history with previous content so revert_file can restore it
        self._history.setdefault(str(target_path), []).append(old_content)

        target_path.unlink()

        return WorkspaceFileChange(
            path=relative_path,
            action="delete",
            diff=diff,
            previous_content=old_content,
        )

    def delete_model(self, model_name: str, layer: Optional[str] = None) -> List[WorkspaceFileChange]:
        """
        Locates and deletes all files related to model_name (e.g. .sql and .yml) inside models/.
        Tracks rollback history for all deleted files.
        """
        deleted_changes: List[WorkspaceFileChange] = []
        search_dir = (self.allowed_base_dir / layer) if layer else self.allowed_base_dir

        if not search_dir.exists():
            return deleted_changes

        # Find exact matches like <model_name>.sql, <model_name>.yml, <model_name>.yaml
        for ext in (".sql", ".yml", ".yaml"):
            for found_file in search_dir.rglob(f"{model_name}{ext}"):
                rel = str(found_file.relative_to(self.allowed_base_dir))
                deleted_changes.append(self.delete_model_file(rel))

        # Also inspect YAML schema files in the directory to see if the model entry should be removed
        for schema_file in search_dir.rglob("*.yml"):
            try:
                import yaml
                content = yaml.safe_load(schema_file.read_text(encoding="utf-8"))
                if content and isinstance(content, dict) and "models" in content:
                    original_models = content["models"]
                    filtered_models = [m for m in original_models if m.get("name") != model_name]
                    if len(filtered_models) < len(original_models):
                        if len(filtered_models) == 0 and schema_file.stem == model_name:
                            # It's a dedicated schema file and now empty, already handled or will delete
                            pass
                        else:
                            content["models"] = filtered_models
                            new_yaml_text = yaml.dump(content, sort_keys=False)
                            rel = str(schema_file.relative_to(self.allowed_base_dir))
                            deleted_changes.append(self.write_model_file(rel, new_yaml_text))
            except Exception:
                pass

        return deleted_changes

    def revert_file(self, relative_path: str) -> bool:
        """Reverts the last modification to the specified file."""
        target_path = self._validate_path(relative_path)
        path_str = str(target_path)
        if path_str not in self._history or not self._history[path_str]:
            return False

        previous_content = self._history[path_str].pop()
        if previous_content is None:
            # File was originally created in this session, so delete it
            if target_path.exists():
                target_path.unlink()
        else:
            # File was either modified or deleted, so restore the previous content
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(previous_content, encoding="utf-8")

        return True

    def list_modified_files(self) -> List[str]:
        """Returns list of relative paths modified in this manager lifecycle."""
        res: List[str] = []
        for p in self._history.keys():
            try:
                rel = str(Path(p).relative_to(self.config.dbt_project_dir))
                res.append(rel)
            except ValueError:
                res.append(p)
        return res
