"""Project Discovery Service for inspecting the dbt project and models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from harness.core.config import HarnessConfig, get_config
from harness.core.contracts import (
    ColumnMetadata,
    EntityDefinition,
    LineageGraph,
    ModelMetadata,
    ProjectOverview,
)


class DiscoveryService:
    """Discovers dbt models, schemas, lineage, and entity definitions."""

    def __init__(self, config: Optional[HarnessConfig] = None) -> None:
        self.config = config or get_config()

    def discover_project(self) -> ProjectOverview:
        manifest_data = self._load_manifest()
        models = self.list_models()
        layers_map: Dict[str, List[str]] = {}
        for m in models:
            layers_map.setdefault(m.layer, []).append(m.name)

        entities = [e.entity_name for e in self.get_entity_definitions()]

        dbt_version = "1.12.6"
        if manifest_data:
            dbt_version = manifest_data.get("metadata", {}).get("dbt_version", dbt_version)

        return ProjectOverview(
            project_name="anac_lakehouse",
            dbt_version=dbt_version,
            total_models=len(models),
            layers=layers_map,
            entities=entities,
            database_path=str(self.config.database_path),
        )

    def list_models(self, layer: Optional[str] = None) -> List[ModelMetadata]:
        manifest = self._load_manifest()
        if manifest:
            models = self._models_from_manifest(manifest)
        else:
            models = self._models_from_filesystem()

        if layer:
            layer_lower = layer.lower()
            return [m for m in models if m.layer.lower() == layer_lower]
        return models

    def get_model_details(self, model_name: str) -> Optional[ModelMetadata]:
        all_models = self.list_models()
        for m in all_models:
            if m.name == model_name:
                return m
        return None

    def get_model_lineage(self, model_name: str) -> LineageGraph:
        manifest = self._load_manifest()
        upstream: List[str] = []
        downstream: List[str] = []

        if manifest:
            parent_map = manifest.get("parent_map", {})
            child_map = manifest.get("child_map", {})

            for uid, parents in parent_map.items():
                if uid.startswith("model.anac_lakehouse.") and uid.endswith(f".{model_name}"):
                    upstream = [p.split(".")[-1] for p in parents if p.startswith("model.") or p.startswith("seed.")]

            for uid, children in child_map.items():
                if uid.startswith("model.anac_lakehouse.") and uid.endswith(f".{model_name}"):
                    downstream = [c.split(".")[-1] for c in children if c.startswith("model.")]
        else:
            # Fallback simple filesystem reference check
            model = self.get_model_details(model_name)
            if model and model.raw_code:
                import re
                refs = re.findall(r"ref\(['\"](.*?)['\"]\)", model.raw_code)
                upstream = list(set(refs))

        return LineageGraph(model_name=model_name, upstream=upstream, downstream=downstream)

    def get_entity_definitions(self) -> List[EntityDefinition]:
        """Discovers entities primarily from trusted dimension models."""
        trusted_models = self.list_models(layer="trusted")
        entities: List[EntityDefinition] = []

        for m in trusted_models:
            # Entity name derived from dim_<name>
            entity_name = m.name.replace("dim_", "")
            pk: Optional[str] = None
            features: List[str] = []

            for col_name, col in m.columns.items():
                if "unique" in col.tests:
                    pk = col_name
                if col_name.startswith("is_") or col_name.startswith("has_") or "anos" in col_name:
                    features.append(col_name)

            entities.append(
                EntityDefinition(
                    entity_name=entity_name,
                    model_name=m.name,
                    primary_key=pk,
                    description=m.description,
                    features=features,
                    grain=f"1 row per {entity_name} ({pk})" if pk else None,
                )
            )

        return entities

    def _load_manifest(self) -> Optional[Dict[str, Any]]:
        manifest_path = self.config.dbt_target_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _models_from_manifest(self, manifest: Dict[str, Any]) -> List[ModelMetadata]:
        nodes = manifest.get("nodes", {})
        models: List[ModelMetadata] = []

        for unique_id, node in nodes.items():
            if not unique_id.startswith("model."):
                continue

            name = node.get("name", "")
            original_path = node.get("original_file_path", "")
            raw_code = node.get("raw_code", "")
            compiled_code = node.get("compiled_code", "")
            materialized = node.get("config", {}).get("materialized", "table")
            description = node.get("description", "")
            relation_name = node.get("relation_name", "")

            # Determine layer from path or tags/schema
            layer = self._determine_layer(original_path, node.get("schema", ""))

            # Extract columns & tests
            columns: Dict[str, ColumnMetadata] = {}
            for col_name, col_data in node.get("columns", {}).items():
                columns[col_name] = ColumnMetadata(
                    name=col_name,
                    data_type=col_data.get("data_type"),
                    description=col_data.get("description"),
                )

            # Match tests on this model
            for test_id, test_node in nodes.items():
                if test_id.startswith("test."):
                    attached = test_node.get("attached_node")
                    if attached == unique_id:
                        col = test_node.get("column_name")
                        test_name = test_node.get("test_metadata", {}).get("name", "")
                        if not test_name:
                            test_name = test_node.get("name", "").split("_")[0]
                        if col and col in columns:
                            columns[col].tests.append(test_name)

            models.append(
                ModelMetadata(
                    name=name,
                    unique_id=unique_id,
                    layer=layer,
                    relation_name=relation_name,
                    materialized=materialized,
                    path=original_path,
                    description=description,
                    columns=columns,
                    depends_on_nodes=node.get("depends_on", {}).get("nodes", []),
                    raw_code=raw_code,
                    compiled_code=compiled_code,
                )
            )

        return models

    def _models_from_filesystem(self) -> List[ModelMetadata]:
        models_dir = self.config.dbt_project_dir / "models"
        models: List[ModelMetadata] = []
        if not models_dir.exists():
            return models

        # Load schemas
        schemas: Dict[str, Any] = {}
        for schema_file in models_dir.rglob("*.yml"):
            try:
                with open(schema_file, "r", encoding="utf-8") as f:
                    content = yaml.safe_load(f)
                    if content and "models" in content:
                        for m in content["models"]:
                            schemas[m.get("name", "")] = m
            except Exception:
                continue

        for sql_file in models_dir.rglob("*.sql"):
            model_name = sql_file.stem
            rel_path = str(sql_file.relative_to(self.config.dbt_project_dir))
            layer = self._determine_layer(rel_path, "")

            raw_code = sql_file.read_text(encoding="utf-8")
            yaml_info = schemas.get(model_name, {})

            cols: Dict[str, ColumnMetadata] = {}
            for c in yaml_info.get("columns", []):
                col_name = c.get("name")
                tests: List[str] = []
                for t in c.get("tests", []):
                    if isinstance(t, str):
                        tests.append(t)
                    elif isinstance(t, dict):
                        tests.extend(list(t.keys()))
                cols[col_name] = ColumnMetadata(
                    name=col_name,
                    description=c.get("description"),
                    tests=tests,
                )

            models.append(
                ModelMetadata(
                    name=model_name,
                    unique_id=f"model.anac_lakehouse.{model_name}",
                    layer=layer,
                    path=rel_path,
                    materialized="table" if layer != "staging" else "view",
                    description=yaml_info.get("description"),
                    columns=cols,
                    raw_code=raw_code,
                )
            )

        return models

    @staticmethod
    def _determine_layer(path_str: str, schema: str) -> str:
        p = path_str.lower()
        if "landing" in p or schema == "landing":
            return "landing"
        if "raw" in p or schema == "raw":
            return "raw"
        if "staging" in p or schema == "staging":
            return "staging"
        if "trusted" in p or schema == "trusted":
            return "trusted"
        if "reports" in p or schema == "reports":
            return "reports"
        return "custom"

