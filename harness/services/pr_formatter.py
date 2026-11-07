"""Pull Request description formatter with demands, tests, markdown tables, and profiling."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from harness.core.contracts import ValidationReport


class PRFormatter:
    """Builds clean, comprehensive Markdown PR bodies matching the exact user specification."""

    @staticmethod
    def build_pr_body(
        demand: str,
        target_models: List[Dict[str, Any]],
        validation_reports: List[ValidationReport],
        profiling_data: Dict[str, Dict[str, Any]],
    ) -> str:
        lines = [
            "## 📋 Demanda Solicitada",
            f"> {demand}",
            "",
            "---",
            "",
            "## 🧪 Testes do dbt",
        ]

        # 1. dbt test summary
        all_passed = all(r.tests_passed and r.build_passed for r in validation_reports)
        if all_passed:
            lines.append("✅ **Todos os testes do dbt passaram com sucesso (`dbt test` & `dbt build`).**")
        else:
            lines.append("⚠️ **Houve falhas ou avisos na execução dos testes do dbt.**")

        lines.append("")
        for rep in validation_reports:
            status_icon = "✅" if rep.passed else "❌"
            lines.append(f"- {status_icon} **Modelo `{rep.model_name}`**:")
            lines.append(f"  - Compilação: {'✅ Passou' if rep.compilation_passed else '❌ Falhou'}")
            lines.append(f"  - Build & Execução: {'✅ Passou' if rep.build_passed else '❌ Falhou'}")
            lines.append(f"  - Testes de Dados: {'✅ Passou' if rep.tests_passed else '❌ Falhou'}")
            lines.append(f"  - Diretrizes ECM: {'✅ Passou' if rep.guidelines_passed else '❌ Falhou'}")
            if rep.dbt_failures:
                for f in rep.dbt_failures:
                    lines.append(f"    - Erro: `{f.get('message')}`")

        lines.extend([
            "",
            "---",
            "",
            "## 📊 Tabelas Geradas",
            "",
            "| Modelo | Camada | Materialização | Granularidade | Chave Primária | Testes dbt |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for m in target_models:
            name = m.get("model_name", "")
            layer = m.get("layer", "trusted")
            mat = m.get("materialized", "table")
            grain = m.get("grain", "1 linha por entidade")
            pk = m.get("primary_key", "-")
            tests = ", ".join(m.get("tests", ["unique", "not_null"]))
            lines.append(f"| `{name}` | `{layer}` | `{mat}` | {grain} | `{pk}` | `{tests}` |")

        lines.extend([
            "",
            "---",
            "",
            "## 🔍 Profiling dos Dados",
            "",
        ])

        for table_name, profile in profiling_data.items():
            row_count = profile.get("row_count", 0)
            pk_col = profile.get("primary_key", "-")
            is_unique = profile.get("is_unique", True)
            null_rates = profile.get("null_rates", {})
            sample_rows = profile.get("preview_sample_rows", [])
            cols = profile.get("preview_columns", [])

            lines.extend([
                f"### Tabela: `{table_name}`",
                f"- **Volumetria**: `{row_count:,}` registros".replace(",", "."),
                f"- **Unicidade da Chave (`{pk_col}`)**: {'✅ 100% Única (0 duplicatas)' if is_unique else '❌ Duplicatas encontradas'}",
                "",
                "#### Taxas de Nulidade por Coluna:",
                "| Coluna | % Nulos |",
                "| :--- | :--- |",
            ])

            for col, rate in list(null_rates.items())[:10]:
                lines.append(f"| `{col}` | `{rate}%` |")

            if len(null_rates) > 10:
                lines.append(f"| *... mais {len(null_rates) - 10} colunas* | - |")

            if sample_rows and cols:
                lines.extend([
                    "",
                    "#### Amostra dos Dados Gerados:",
                    "| " + " | ".join(cols[:6]) + " |",
                    "| " + " | ".join([":---"] * len(cols[:6])) + " |",
                ])
                for row in sample_rows[:3]:
                    row_strs = [str(v) if v is not None else "NULL" for v in row[:6]]
                    lines.append("| " + " | ".join(row_strs) + " |")

            lines.append("")

        lines.extend([
            "---",
            "*Gerado automaticamente pelo **Agentic dbt Development Harness** com Google ADK.*",
        ])

        return "\n".join(lines)

