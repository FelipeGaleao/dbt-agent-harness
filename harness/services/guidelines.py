"""Guidelines and Modeling Policies Service."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from harness.core.config import HarnessConfig, get_config
from harness.core.contracts import ComplianceCheckResult, GuidelineRule


class GuidelinesService:
    """Reads project guidelines and provides programmatic rule checking."""

    def __init__(self, config: Optional[HarnessConfig] = None) -> None:
        self.config = config or get_config()
        self.guidelines_file = self.config.guidelines_dir / "entity_centric_modeling_guideline.md"

    def get_raw_guidelines(self) -> str:
        if self.guidelines_file.exists():
            return self.guidelines_file.read_text(encoding="utf-8")
        return "No guidelines document found."

    def get_rules(self) -> List[GuidelineRule]:
        return [
            GuidelineRule(
                id="ECM-001",
                title="Trusted Layer Table Naming",
                category="Naming Conventions",
                description="Trusted layer models must begin with 'dim_' (wide entity), 'fct_' (activity), or 'bridge_'.",
                severity="error",
            ),
            GuidelineRule(
                id="ECM-002",
                title="Staging Layer Table Naming",
                category="Naming Conventions",
                description="Staging models must follow pattern 'stg_<source>__<entity>'.",
                severity="error",
            ),
            GuidelineRule(
                id="ECM-003",
                title="Primary Key Unique and Not Null Tests",
                category="Data Quality",
                description="Entity primary key column must have both 'unique' and 'not_null' tests in schema YAML.",
                severity="error",
            ),
            GuidelineRule(
                id="ECM-004",
                title="Boolean Column Naming Prefix",
                category="Naming Conventions",
                description="Boolean indicator columns must begin with 'is_' or 'has_'.",
                severity="warning",
            ),
            GuidelineRule(
                id="ECM-005",
                title="Boolean Accepted Values Test",
                category="Data Quality",
                description="Boolean indicator columns should define 'not_null' and 'accepted_values: [true, false]'.",
                severity="warning",
            ),
            GuidelineRule(
                id="ECM-006",
                title="Resilient Numeric and Date Parsing",
                category="SQL Standards",
                description="Staging models parsing untyped sources should prefer try_cast / try_strptime over direct cast.",
                severity="warning",
            ),
            GuidelineRule(
                id="ECM-007",
                title="Model Documentation Required",
                category="Documentation",
                description="All models in trusted layer must have a description in schema YAML explaining entity grain.",
                severity="warning",
            ),
            GuidelineRule(
                id="ECM-008",
                title="Trusted Layer Lineage Dependency",
                category="Architectural Layers",
                description="Trusted layer models cannot depend on other trusted models. They must read strictly from staging (stg_) or raw.",
                severity="error",
            ),
            GuidelineRule(
                id="ECM-009",
                title="Reports Layer Lineage Dependency",
                category="Architectural Layers",
                description="Reports layer models must strictly read from the trusted layer (dim_* or fct_*). They cannot read from staging, raw, or landing.",
                severity="error",
            ),
        ]

    def validate_model_compliance(
        self,
        model_name: str,
        sql_content: str,
        yaml_content: Optional[str] = None,
        layer: str = "trusted",
    ) -> List[ComplianceCheckResult]:
        """Validates a model deterministically against ECM guidelines."""
        results: List[ComplianceCheckResult] = []
        layer_lower = layer.lower()

        # Rule ECM-001: Trusted naming
        if layer_lower == "trusted":
            valid_prefix = model_name.startswith("dim_") or model_name.startswith("fct_") or model_name.startswith("bridge_")
            results.append(
                ComplianceCheckResult(
                    rule_id="ECM-001",
                    rule_title="Trusted Layer Table Naming",
                    passed=valid_prefix,
                    details=f"Model name '{model_name}' starts with dim_/fct_/bridge_" if valid_prefix else f"Model name '{model_name}' violates trusted naming convention (must start with dim_, fct_, or bridge_).",
                    severity="error",
                )
            )

            # Rule ECM-008: Trusted lineage restriction (trusted cannot read from trusted)
            refs = re.findall(r"ref\(\s*['\"]([^'\"]+)['\"]\s*\)", sql_content)
            trusted_refs = [
                r for r in refs
                if r.startswith("dim_") or r.startswith("fct_") or r.startswith("bridge_")
            ]
            has_trusted_dependency = len(trusted_refs) > 0
            results.append(
                ComplianceCheckResult(
                    rule_id="ECM-008",
                    rule_title="Trusted Layer Lineage Dependency",
                    passed=not has_trusted_dependency,
                    details=(
                        f"Violates lineage rule: trusted model '{model_name}' directly references other trusted model(s): {', '.join(trusted_refs)}. Trusted models must read strictly from staging (stg_) or raw."
                        if has_trusted_dependency
                        else f"Model '{model_name}' respects trusted lineage (reads only from staging/raw)."
                    ),
                    severity="error",
                )
            )

        # Rule ECM-002: Staging naming
        if layer_lower == "staging":
            valid_stg = model_name.startswith("stg_") and "__" in model_name
            results.append(
                ComplianceCheckResult(
                    rule_id="ECM-002",
                    rule_title="Staging Layer Table Naming",
                    passed=valid_stg,
                    details=f"Model name '{model_name}' follows stg_<source>__<entity>" if valid_stg else f"Model name '{model_name}' should follow 'stg_<source>__<entity>'.",
                    severity="error",
                )
            )

        # Rule ECM-009: Reports layer lineage restriction (reports must strictly read from trusted)
        if layer_lower == "reports":
            refs = re.findall(r"ref\(\s*['\"]([^'\"]+)['\"]\s*\)", sql_content)
            non_trusted_refs = [
                r for r in refs
                if not (r.startswith("dim_") or r.startswith("fct_") or r.startswith("bridge_"))
            ]
            valid_reports_lineage = len(refs) > 0 and len(non_trusted_refs) == 0
            results.append(
                ComplianceCheckResult(
                    rule_id="ECM-009",
                    rule_title="Reports Layer Lineage Dependency",
                    passed=valid_reports_lineage,
                    details=(
                        f"Model '{model_name}' correctly consumes strictly from trusted layer models."
                        if valid_reports_lineage
                        else (
                            f"Violates lineage rule: reports model '{model_name}' must read strictly from the trusted layer (dim_*, fct_*). Found invalid references: {', '.join(non_trusted_refs) if non_trusted_refs else 'no references found'}."
                        )
                    ),
                    severity="error",
                )
            )

        # Rule ECM-006: Resilient Parsing in staging
        if layer_lower == "staging":
            has_raw_cast = bool(re.search(r"\bcast\s*\(", sql_content, re.IGNORECASE))
            has_try_cast = bool(re.search(r"\btry_cast\s*\(", sql_content, re.IGNORECASE))
            if has_raw_cast and not has_try_cast:
                results.append(
                    ComplianceCheckResult(
                        rule_id="ECM-006",
                        rule_title="Resilient Numeric and Date Parsing",
                        passed=False,
                        details="SQL uses direct cast() without try_cast(). Prefer try_cast for raw source parsing.",
                        severity="warning",
                    )
                )
            else:
                results.append(
                    ComplianceCheckResult(
                        rule_id="ECM-006",
                        rule_title="Resilient Numeric and Date Parsing",
                        passed=True,
                        details="Resilient parsing respected or no direct unhandled cast found.",
                        severity="warning",
                    )
                )

        # YAML validations
        if yaml_content:
            try:
                parsed_yaml = yaml.safe_load(yaml_content)
                models_list = parsed_yaml.get("models", []) if isinstance(parsed_yaml, dict) else []
                target_model_yaml = next((m for m in models_list if m.get("name") == model_name), None)

                if target_model_yaml:
                    # ECM-007 Documentation
                    desc = target_model_yaml.get("description", "")
                    has_desc = bool(desc and len(desc.strip()) > 10)
                    results.append(
                        ComplianceCheckResult(
                            rule_id="ECM-007",
                            rule_title="Model Documentation Required",
                            passed=has_desc,
                            details="Model has detailed documentation." if has_desc else "Model description is missing or too brief.",
                            severity="warning",
                        )
                    )

                    # ECM-003: PK tests
                    columns = target_model_yaml.get("columns", [])
                    has_pk_tests = False
                    for col in columns:
                        tests = col.get("tests", [])
                        test_names = []
                        for t in tests:
                            if isinstance(t, str):
                                test_names.append(t)
                            elif isinstance(t, dict):
                                test_names.extend(t.keys())
                        if "unique" in test_names and "not_null" in test_names:
                            has_pk_tests = True
                            break

                    results.append(
                        ComplianceCheckResult(
                            rule_id="ECM-003",
                            rule_title="Primary Key Unique and Not Null Tests",
                            passed=has_pk_tests,
                            details="At least one column has both 'unique' and 'not_null' tests." if has_pk_tests else "No column defined with both 'unique' and 'not_null' tests in YAML.",
                            severity="error" if layer_lower == "trusted" else "warning",
                        )
                    )

                    # ECM-004 & ECM-005: Boolean flags
                    for col in columns:
                        col_name = col.get("name", "")
                        if col_name.startswith("is_") or col_name.startswith("has_"):
                            tests = col.get("tests", [])
                            has_acc_val = any("accepted_values" in (t if isinstance(t, str) else list(t.keys())) for t in tests)
                            results.append(
                                ComplianceCheckResult(
                                    rule_id="ECM-005",
                                    rule_title=f"Boolean Flag Tests ({col_name})",
                                    passed=has_acc_val,
                                    details=f"Column '{col_name}' has accepted_values test" if has_acc_val else f"Column '{col_name}' is a boolean flag but lacks accepted_values test.",
                                    severity="warning",
                                )
                            )
            except Exception as e:
                results.append(
                    ComplianceCheckResult(
                        rule_id="ECM-YAML-ERR",
                        rule_title="YAML Schema Parsing",
                        passed=False,
                        details=f"Failed to parse YAML content: {e}",
                        severity="error",
                    )
                )

        return results

