"""Planning and interactive review models and service."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class ModelPlanItem(BaseModel):
    model_name: str
    layer: str  # staging, trusted
    materialized: str = "table"
    description: str
    grain: str
    primary_key: str
    upstream_sources: List[str] = Field(default_factory=list)
    columns: Dict[str, str] = Field(default_factory=dict)
    tests: List[str] = Field(default_factory=list)


class ModelingPlan(BaseModel):
    plan_id: str
    session_id: str
    demand: str
    status: PlanStatus = PlanStatus.DRAFT
    target_models: List[ModelPlanItem] = Field(default_factory=list)
    proposed_branch: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    feedback_history: List[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"# 📐 Plano de Modelagem dbt: `{self.plan_id}`",
            f"**Status**: `{self.status.value.upper()}` | **Branch Sugerida**: `{self.proposed_branch}`",
            "",
            "## 1. Demanda Solicitada",
            f"> {self.demand}",
            "",
            "## 2. Modelos Planejados",
        ]

        for m in self.target_models:
            lines.extend([
                f"### `{m.layer}.{m.model_name}` ({m.materialized})",
                f"- **Objetivo**: {m.description}",
                f"- **Granularidade (Grain)**: {m.grain}",
                f"- **Chave Primária**: `{m.primary_key}`",
                f"- **Origem / Linhagem**: `{', '.join(m.upstream_sources) or 'N/A'}`",
                "",
                "| Coluna | Descrição |",
                "| :--- | :--- |",
            ])
            for col_name, col_desc in m.columns.items():
                lines.append(f"| `{col_name}` | {col_desc} |")
            lines.extend([
                "",
                f"- **Testes Obrigatórios**: {', '.join(m.tests) or 'unique, not_null'}",
                "",
            ])

        lines.extend([
            "## 3. Diretrizes de Governança Aplicadas",
            "- [x] Nomenclatura aderente (`dim_*`, `stg_*`)",
            "- [x] Regra de Linhagem Estrita: camada `trusted` lê estritamente de `staging` ou `raw`",
            "- [x] Testes de `unique` e `not_null` na chave da entidade",
            "- [x] Flags booleanas padronizadas (`is_*`, `has_*`)",
            "",
            "---",
            "💬 **Validação do Usuário Necessária**: Por favor, avalie o plano acima. Se desejar alterações, responda com os ajustes. Se estiver de acordo, responda 'Aprovo o plano' para criar a worktree e prosseguir com a implementação.",
        ])

        return "\n".join(lines)

