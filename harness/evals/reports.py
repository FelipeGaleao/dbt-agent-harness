"""Formatting and reporting utilities for validation results."""

from __future__ import annotations

from harness.core.contracts import ValidationReport


class ValidationReporter:
    """Formats ValidationReport into human-readable and agent-digestible text or markdown."""

    @staticmethod
    def format_markdown(report: ValidationReport) -> str:
        status_badge = "✅ PASSED" if report.passed else "❌ FAILED"
        lines = [
            f"# Validation Report: `{report.model_name}` ({status_badge})",
            f"**Timestamp**: {report.timestamp}",
            "",
            "## Summary",
            f"- **Compilation**: {'✅ Passed' if report.compilation_passed else '❌ Failed'}",
            f"- **dbt Build**: {'✅ Passed' if report.build_passed else '❌ Failed'}",
            f"- **dbt Tests**: {'✅ Passed' if report.tests_passed else '❌ Failed'}",
            f"- **Guidelines Compliance**: {'✅ Passed' if report.guidelines_passed else '❌ Failed'}",
            "",
        ]

        if report.compliance_checks:
            lines.append("## Policy Compliance Checks")
            for c in report.compliance_checks:
                icon = "✅" if c.passed else ("⚠️" if c.severity == "warning" else "❌")
                lines.append(f"- {icon} **{c.rule_id} ({c.rule_title})**: {c.details}")
            lines.append("")

        if report.dbt_failures:
            lines.append("## Failures & Errors")
            for f in report.dbt_failures:
                msg = f.get("message", "Unknown error")
                uid = f.get("unique_id", "")
                lines.append(f"- **{uid or 'dbt'}**: `{msg}`")
            lines.append("")

        if report.evidence:
            lines.append("## Database Evidence")
            for k, v in report.evidence.items():
                lines.append(f"- **{k}**: {v}")
            lines.append("")

        if report.warnings:
            lines.append("## Warnings")
            for w in report.warnings:
                lines.append(f"- ⚠️ {w}")
            lines.append("")

        if report.remaining_uncertainties:
            lines.append("## Remaining Uncertainties")
            for u in report.remaining_uncertainties:
                lines.append(f"- ❓ {u}")
            lines.append("")

        return "\n".join(lines)

