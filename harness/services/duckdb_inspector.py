"""DuckDB Inspection Service with read-only safeguards and lock resilience."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional
import duckdb

from harness.core.config import HarnessConfig, get_config
from harness.core.contracts import QueryResult, TablePreview


class DuckDBInspector:
    """Safe analytical inspection of local DuckDB database."""

    # Disallow destructive/write statements
    FORBIDDEN_KEYWORDS = {
        "insert", "update", "delete", "drop", "create", "alter", "truncate",
        "copy", "attach", "detach", "vacuum", "call", "pragma"
    }

    def __init__(self, config: Optional[HarnessConfig] = None) -> None:
        self.config = config or get_config()
        self.db_path = self.config.database_path

    def _get_connection(self) -> tuple[duckdb.DuckDBPyConnection, Optional[str]]:
        """
        Attempts direct read_only connection first.
        If locked by another process (e.g. duckdb CLI/UI), falls back to a temporary snapshot file.
        Returns (connection, temp_file_path_or_none).
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database file does not exist at '{self.db_path}'")

        try:
            # Try direct read-only
            conn = duckdb.connect(str(self.db_path), read_only=True)
            return conn, None
        except duckdb.IOException as e:
            # If lock collision occurs, take a snapshot copy
            temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            temp_db_path = temp_db.name
            temp_db.close()

            # Read via standard file copy to bypass DuckDB's cooperative flock
            with open(self.db_path, "rb") as src, open(temp_db_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

            conn = duckdb.connect(temp_db_path, read_only=True)
            return conn, temp_db_path

    def execute_query(self, sql: str, limit: int = 100) -> QueryResult:
        """Executes a bounded, read-only analytical query."""
        clean_sql = sql.strip().rstrip(";")
        first_word = clean_sql.split()[0].lower() if clean_sql else ""

        # Only allow SELECT, SHOW, DESCRIBE, EXPLAIN
        if first_word not in ("select", "show", "describe", "explain", "with"):
            raise PermissionError(
                f"Query rejected: Only read-only queries (SELECT, WITH, SHOW, DESCRIBE, EXPLAIN) are permitted. Received: '{first_word}'"
            )

        # Check for embedded forbidden tokens
        for forbidden in self.FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{forbidden}\b", clean_sql, re.IGNORECASE):
                # allow 'create' only if inside quotes or part of select expression, but reject DDL
                if forbidden in ("create", "drop", "alter", "truncate", "insert", "update", "delete"):
                    raise PermissionError(f"Query rejected: statement contains restricted keyword '{forbidden}'")

        # Enforce limit if SELECT / WITH and not already bounded
        bounded_sql = clean_sql
        if first_word in ("select", "with") and not re.search(r"\blimit\s+\d+", clean_sql, re.IGNORECASE):
            bounded_sql = f"{clean_sql} LIMIT {limit}"

        start_time = time.time()
        conn, temp_file = self._get_connection()
        try:
            cursor = conn.execute(bounded_sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            duration = time.time() - start_time
            # convert any tuples to lists and serialize date/datetime/decimals to str for JSON safety
            def _clean_val(v: Any) -> Any:
                import datetime
                if isinstance(v, (datetime.date, datetime.datetime, datetime.time)):
                    return v.isoformat()
                return v

            rows_as_lists = [[_clean_val(v) for v in r] for r in rows]
            return QueryResult(
                columns=columns,
                rows=rows_as_lists,
                row_count=len(rows_as_lists),
                execution_time_seconds=round(duration, 3),
            )
        finally:
            conn.close()
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

    def list_schemas(self) -> List[str]:
        res = self.execute_query("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('information_schema', 'pg_catalog') ORDER BY schema_name;")
        return [r[0] for r in res.rows]

    def list_tables(self, schema: Optional[str] = None) -> List[Dict[str, str]]:
        if schema:
            sql = f"SELECT table_schema, table_name, table_type FROM information_schema.tables WHERE table_schema = '{schema}' ORDER BY table_name;"
        else:
            sql = "SELECT table_schema, table_name, table_type FROM information_schema.tables WHERE table_schema NOT IN ('information_schema', 'pg_catalog') ORDER BY table_schema, table_name;"
        res = self.execute_query(sql)
        return [{"schema": r[0], "table": r[1], "type": r[2]} for r in res.rows]

    def describe_table(self, table_name: str, schema: Optional[str] = None) -> List[Dict[str, Any]]:
        target = f"{schema}.{table_name}" if schema else table_name
        try:
            res = self.execute_query(f"DESCRIBE {target};")
            # columns: column_name, column_type, null, key, default, extra
            return [
                {
                    "column_name": r[0],
                    "data_type": r[1],
                    "null": r[2] if len(r) > 2 else "YES",
                }
                for r in res.rows
            ]
        except Exception:
            return []

    def get_row_count(self, table_name: str, schema: Optional[str] = None) -> int:
        target = f"{schema}.{table_name}" if schema else table_name
        try:
            res = self.execute_query(f"SELECT COUNT(*) FROM {target};")
            return int(res.rows[0][0]) if res.rows else 0
        except Exception:
            return -1

    def check_primary_key_uniqueness(self, table_name: str, pk_column: str, schema: Optional[str] = None) -> Dict[str, Any]:
        """Checks for duplicate primary keys in the specified table."""
        target = f"{schema}.{table_name}" if schema else table_name
        try:
            sql = f"""
                SELECT {pk_column}, COUNT(*) as cnt
                FROM {target}
                GROUP BY {pk_column}
                HAVING COUNT(*) > 1
                LIMIT 10;
            """
            res = self.execute_query(sql)
            duplicates_found = res.row_count > 0
            return {
                "table": target,
                "pk_column": pk_column,
                "is_unique": not duplicates_found,
                "duplicate_samples": res.rows,
            }
        except Exception as e:
            return {
                "table": target,
                "pk_column": pk_column,
                "error": str(e),
                "is_unique": False,
                "duplicate_samples": [],
            }

    def inspect_null_rates(self, table_name: str, columns: Optional[List[str]] = None, schema: Optional[str] = None) -> Dict[str, float]:
        """Calculates null rate percentage for columns."""
        target = f"{schema}.{table_name}" if schema else table_name
        if not columns:
            desc = self.describe_table(table_name, schema=schema)
            columns = [c["column_name"] for c in desc]

        if not columns:
            return {}

        select_clauses = [
            f"ROUND(COUNT(CASE WHEN {col} IS NULL THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2) AS null_pct_{col}"
            for col in columns
        ]
        sql = f"SELECT {', '.join(select_clauses)} FROM {target};"
        res = self.execute_query(sql)
        if not res.rows:
            return {}

        rates: Dict[str, float] = {}
        for idx, col in enumerate(columns):
            val = res.rows[0][idx]
            rates[col] = float(val) if val is not None else 0.0
        return rates

    def preview_table(self, table_name: str, schema: Optional[str] = None, limit: int = 5) -> TablePreview:
        target = f"{schema}.{table_name}" if schema else table_name
        res = self.execute_query(f"SELECT * FROM {target} LIMIT {limit};")
        return TablePreview(
            schema_name=schema or "main",
            table_name=table_name,
            columns=res.columns,
            rows=res.rows,
            total_rows_sampled=res.row_count,
        )

