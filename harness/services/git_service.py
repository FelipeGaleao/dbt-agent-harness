"""Git Worktree and GitHub PR management service."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from harness.core.config import HarnessConfig, get_config


class GitService:
    """Manages Git worktrees, feature branches, commits, pushes, and GitHub Pull Requests."""

    def __init__(self, config: Optional[HarnessConfig] = None) -> None:
        self.config = config or get_config()
        self.worktree_base_dir = self.config.project_root / ".worktrees"

    def create_feature_worktree(self, session_id: str, branch_name: str) -> Path:
        """
        Creates an isolated Git worktree for the session at .worktrees/<session_id>.
        The worktree is checked out on a new branch based on current HEAD.
        """
        self.worktree_base_dir.mkdir(parents=True, exist_ok=True)
        worktree_path = self.worktree_base_dir / session_id

        # Clean existing if necessary
        if worktree_path.exists():
            self.cleanup_worktree(worktree_path, force=True)

        cmd = ["git", "worktree", "add", "-b", branch_name, str(worktree_path)]
        res = subprocess.run(cmd, cwd=str(self.config.project_root), capture_output=True, text=True)
        if res.returncode != 0:
            # If branch already exists, checkout without -b
            if "already exists" in res.stderr:
                cmd = ["git", "worktree", "add", str(worktree_path), branch_name]
                res2 = subprocess.run(cmd, cwd=str(self.config.project_root), capture_output=True, text=True)
                if res2.returncode != 0:
                    raise RuntimeError(f"Failed to create git worktree: {res2.stderr}")
            else:
                raise RuntimeError(f"Failed to create git worktree: {res.stderr}")

        # Ensure database link exists inside worktree pointing directly to root database so all changes persist
        worktree_db_dir = worktree_path / "databases"
        if not worktree_db_dir.exists():
            root_db_dir = self.config.project_root / "databases"
            if root_db_dir.exists():
                try:
                    os.symlink(str(root_db_dir.resolve()), str(worktree_db_dir), target_is_directory=True)
                except OSError:
                    worktree_db_dir.mkdir(parents=True, exist_ok=True)
                    root_db_file = root_db_dir / "anac_lakehouse.db"
                    if root_db_file.exists():
                        try:
                            os.symlink(str(root_db_file.resolve()), str(worktree_db_dir / "anac_lakehouse.db"))
                        except OSError:
                            shutil.copy2(str(root_db_file), str(worktree_db_dir / "anac_lakehouse.db"))

        return worktree_path

    def commit_changes(self, worktree_path: Path, message: str) -> str:
        """Stages all changes inside the worktree and commits them."""
        # Check if there are changes
        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
        )
        if not status_res.stdout.strip():
            return "No changes to commit."

        add_res = subprocess.run(
            ["git", "add", "."],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
        )
        if add_res.returncode != 0:
            raise RuntimeError(f"git add failed: {add_res.stderr}")

        commit_res = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
        )
        if commit_res.returncode != 0:
            raise RuntimeError(f"git commit failed: {commit_res.stderr}")

        return commit_res.stdout.strip()

    def push_branch(self, branch_name: str, remote: str = "origin", worktree_path: Optional[Path] = None) -> str:
        """Pushes the feature branch to the remote git repository."""
        cwd = str(worktree_path) if worktree_path else str(self.config.project_root)
        cmd = ["git", "push", "-u", remote, branch_name]
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"git push failed: {res.stderr}")
        return res.stdout.strip()

    def create_pull_request(
        self,
        title: str,
        body: str,
        branch_name: str,
        base_branch: str = "main",
        worktree_path: Optional[Path] = None,
    ) -> Dict[str, str]:
        """
        Creates a Pull Request on GitHub using the 'gh' CLI.
        Returns a dict with 'url' and 'status'.
        """
        cwd = str(worktree_path) if worktree_path else str(self.config.project_root)

        # First check if a PR already exists for this branch
        check_cmd = ["gh", "pr", "view", branch_name, "--json", "url"]
        check_res = subprocess.run(check_cmd, cwd=cwd, capture_output=True, text=True)
        if check_res.returncode == 0:
            import json
            try:
                data = json.loads(check_res.stdout)
                pr_url = data.get("url", "")
                return {"url": pr_url, "status": "existing"}
            except Exception:
                pass

        # Create the PR
        cmd = [
            "gh",
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--head",
            branch_name,
            "--base",
            base_branch,
        ]
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"gh pr create failed: {res.stderr}")

        pr_url = res.stdout.strip()
        return {"url": pr_url, "status": "created"}

    def cleanup_worktree(self, worktree_path: Path, force: bool = False) -> None:
        """Safely removes the worktree."""
        if not worktree_path.exists():
            return

        cmd = ["git", "worktree", "remove", str(worktree_path)]
        if force:
            cmd.insert(3, "--force")

        res = subprocess.run(cmd, cwd=str(self.config.project_root), capture_output=True, text=True)
        if res.returncode != 0 and worktree_path.exists():
            # Force remove directory if git worktree prune didn't completely delete
            shutil.rmtree(str(worktree_path), ignore_errors=True)
            subprocess.run(["git", "worktree", "prune"], cwd=str(self.config.project_root), capture_output=True)

