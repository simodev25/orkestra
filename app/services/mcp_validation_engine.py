"""MCP Validation Engine — multi-rule validation with structured reports.

Validates MCP definitions against:
1. Structural rules (required fields, format)
2. Governance rules (effect_type consistency, approval, audit)
3. Runtime rules (timeout, retry, cost)
4. Contract rules (refs exist)
5. Integration rules (test invocation)

Each rule produces a ValidationFinding with severity, category, and actionable message.
Rules are composable and extensible.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import MCPDefinition

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# Types
# ────────────────────────────────────────────────────────────

class Severity(str, Enum):
    ERROR = "error"       # Blocks lifecycle progression
    WARNING = "warning"   # Should be fixed but doesn't block
    INFO = "info"         # Recommendation


class Category(str, Enum):
    STRUCTURAL = "structural"
    GOVERNANCE = "governance"
    RUNTIME = "runtime"
    CONTRACT = "contract"
    INTEGRATION = "integration"


@dataclass
class ValidationFinding:
    rule_id: str
    category: str
    severity: str
    message: str
    field: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationReport:
    mcp_id: str
    valid: bool                              # True if zero errors
    score: int                               # 0-100
    findings: list[ValidationFinding] = field(default_factory=list)
    errors: int = 0
    warnings: int = 0
    infos: int = 0
    categories_checked: list[str] = field(default_factory=list)
    integration_tested: bool = False
    integration_latency_ms: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "mcp_id": self.mcp_id,
            "valid": self.valid,
            "score": self.score,
            "errors": self.errors,
            "warnings": self.warnings,
            "infos": self.infos,
            "categories_checked": self.categories_checked,
            "integration_tested": self.integration_tested,
            "integration_latency_ms": self.integration_latency_ms,
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "category": f.category,
                    "severity": f.severity,
                    "message": f.message,
                    "field": f.field,
                    "suggestion": f.suggestion,
                }
                for f in self.findings
            ],
        }


# ────────────────────────────────────────────────────────────
# Validation Rules
# ────────────────────────────────────────────────────────────

VALID_EFFECT_TYPES = {"read", "search", "compute", "generate", "validate", "write", "act"}
SENSITIVE_EFFECTS = {"write", "act"}
HIGH_RISK_EFFECTS = {"act"}


def _check_structural(mcp: MCPDefinition) -> list[ValidationFinding]:
    """Check required fields and format."""
    findings = []

    if not mcp.purpose or len(mcp.purpose.strip()) < 5:
        findings.append(ValidationFinding(
            rule_id="STRUCT_001", category=Category.STRUCTURAL, severity=Severity.ERROR,
            message="Purpose is missing or too short (min 5 characters)",
            field="purpose", suggestion="Describe what this MCP does in a clear, testable sentence",
        ))

    if not mcp.effect_type or mcp.effect_type not in VALID_EFFECT_TYPES:
        findings.append(ValidationFinding(
            rule_id="STRUCT_002", category=Category.STRUCTURAL, severity=Severity.ERROR,
            message=f"Invalid effect_type: '{mcp.effect_type}'. Must be one of {sorted(VALID_EFFECT_TYPES)}",
            field="effect_type",
        ))

    if not mcp.name or len(mcp.name.strip()) < 2:
        findings.append(ValidationFinding(
            rule_id="STRUCT_003", category=Category.STRUCTURAL, severity=Severity.ERROR,
            message="Name is missing or too short",
            field="name",
        ))

    if not mcp.version:
        findings.append(ValidationFinding(
            rule_id="STRUCT_004", category=Category.STRUCTURAL, severity=Severity.WARNING,
            message="Version is not set",
            field="version", suggestion="Use semantic versioning (e.g., 1.0.0)",
        ))

    if not mcp.owner:
        findings.append(ValidationFinding(
            rule_id="STRUCT_005", category=Category.STRUCTURAL, severity=Severity.WARNING,
            message="No owner defined — this MCP has no accountable team",
            field="owner", suggestion="Assign an owner team (e.g., platform_ai_team)",
        ))

    if not mcp.description:
        findings.append(ValidationFinding(
            rule_id="STRUCT_006", category=Category.STRUCTURAL, severity=Severity.INFO,
            message="No description provided — a detailed description helps agent selection",
            field="description",
        ))

    return findings


def _check_governance(mcp: MCPDefinition) -> list[ValidationFinding]:
    """Check governance consistency: approval, audit, criticality vs effect_type."""
    findings = []

    # Sensitive effects should require approval
    if mcp.effect_type in SENSITIVE_EFFECTS and not mcp.approval_required:
        findings.append(ValidationFinding(
            rule_id="GOV_001", category=Category.GOVERNANCE, severity=Severity.ERROR,
            message=f"Effect type '{mcp.effect_type}' is sensitive but approval_required is False",
            field="approval_required",
            suggestion="Set approval_required=True for write/act MCPs to ensure human oversight",
        ))

    # High-criticality should have audit
    if mcp.criticality == "high" and not mcp.audit_required:
        findings.append(ValidationFinding(
            rule_id="GOV_002", category=Category.GOVERNANCE, severity=Severity.ERROR,
            message="High-criticality MCP must have audit_required=True",
            field="audit_required",
            suggestion="Enable audit trail for high-criticality capabilities",
        ))

    # Act effects should be high criticality
    if mcp.effect_type in HIGH_RISK_EFFECTS and mcp.criticality != "high":
        findings.append(ValidationFinding(
            rule_id="GOV_003", category=Category.GOVERNANCE, severity=Severity.WARNING,
            message=f"Effect type 'act' should typically have high criticality (current: {mcp.criticality})",
            field="criticality",
            suggestion="Consider setting criticality to 'high' for capabilities that take real-world actions",
        ))

    # Must have at least one allowed agent
    if not mcp.allowed_agents or len(mcp.allowed_agents) == 0:
        findings.append(ValidationFinding(
            rule_id="GOV_004", category=Category.GOVERNANCE, severity=Severity.WARNING,
            message="No allowed_agents defined — this MCP cannot be used by any agent",
            field="allowed_agents",
            suggestion="Define which agents are authorized to use this MCP",
        ))

    # Write effects without audit is risky
    if mcp.effect_type == "write" and not mcp.audit_required:
        findings.append(ValidationFinding(
            rule_id="GOV_005", category=Category.GOVERNANCE, severity=Severity.WARNING,
            message="Write effects should have audit_required=True for traceability",
            field="audit_required",
        ))

    return findings


def _check_runtime(mcp: MCPDefinition) -> list[ValidationFinding]:
    """Check runtime configuration sanity."""
    findings = []

    if mcp.timeout_seconds <= 0:
        findings.append(ValidationFinding(
            rule_id="RT_001", category=Category.RUNTIME, severity=Severity.ERROR,
            message="Timeout must be greater than 0",
            field="timeout_seconds",
        ))
    elif mcp.timeout_seconds > 120:
        findings.append(ValidationFinding(
            rule_id="RT_002", category=Category.RUNTIME, severity=Severity.WARNING,
            message=f"Timeout is very high ({mcp.timeout_seconds}s) — may cause slow runs",
            field="timeout_seconds",
            suggestion="Consider reducing timeout or optimizing the MCP",
        ))

    if mcp.retry_policy == "aggressive" and mcp.effect_type in SENSITIVE_EFFECTS:
        findings.append(ValidationFinding(
            rule_id="RT_003", category=Category.RUNTIME, severity=Severity.WARNING,
            message="Aggressive retry on a sensitive effect type may cause duplicate side effects",
            field="retry_policy",
            suggestion="Use 'standard' or 'retry_once' for write/act MCPs",
        ))

    if mcp.cost_profile == "high" and mcp.retry_policy in ("aggressive", "retry_twice"):
        findings.append(ValidationFinding(
            rule_id="RT_004", category=Category.RUNTIME, severity=Severity.INFO,
            message="High cost profile with multiple retries can amplify costs",
            field="cost_profile",
        ))

    return findings


def _check_contracts(mcp: MCPDefinition) -> list[ValidationFinding]:
    """Check contract references."""
    findings = []

    if not mcp.input_contract_ref:
        findings.append(ValidationFinding(
            rule_id="CTR_001", category=Category.CONTRACT, severity=Severity.WARNING,
            message="No input contract defined — agents won't know what data to send",
            field="input_contract_ref",
            suggestion="Define a JSON schema for the expected input",
        ))

    if not mcp.output_contract_ref:
        findings.append(ValidationFinding(
            rule_id="CTR_002", category=Category.CONTRACT, severity=Severity.WARNING,
            message="No output contract defined — output cannot be validated",
            field="output_contract_ref",
            suggestion="Define a JSON schema for the expected output",
        ))

    return findings


async def _check_integration(mcp: MCPDefinition) -> tuple[list[ValidationFinding], int | None]:
    """Test the MCP by invoking it and checking the response."""
    findings = []
    latency_ms = None

    try:
        from app.services.mcp_executor import _execute_mcp_tool
        start = time.monotonic()
        result = await _execute_mcp_tool(mcp.id, None, {})
        latency_ms = int((time.monotonic() - start) * 1000)

        if result is None:
            findings.append(ValidationFinding(
                rule_id="INT_001", category=Category.INTEGRATION, severity=Severity.WARNING,
                message="MCP tool not found in local registry — integration test skipped",
                suggestion="Register the tool function in mcp_servers/",
            ))
        else:
            # Test passed
            if latency_ms > mcp.timeout_seconds * 1000:
                findings.append(ValidationFinding(
                    rule_id="INT_002", category=Category.INTEGRATION, severity=Severity.ERROR,
                    message=f"MCP responded in {latency_ms}ms but timeout is {mcp.timeout_seconds * 1000}ms",
                    suggestion="Increase timeout or optimize the MCP",
                ))
            elif latency_ms > mcp.timeout_seconds * 500:
                findings.append(ValidationFinding(
                    rule_id="INT_003", category=Category.INTEGRATION, severity=Severity.WARNING,
                    message=f"MCP latency ({latency_ms}ms) is above 50% of timeout ({mcp.timeout_seconds}s)",
                    suggestion="Consider optimizing or increasing the timeout margin",
                ))

    except Exception as e:
        findings.append(ValidationFinding(
            rule_id="INT_004", category=Category.INTEGRATION, severity=Severity.ERROR,
            message=f"Integration test failed: {str(e)[:200]}",
            suggestion="Check MCP implementation and dependencies",
        ))

    return findings, latency_ms


# ────────────────────────────────────────────────────────────
# Main Validation Entry Point
# ────────────────────────────────────────────────────────────

async def validate_mcp(
    db: AsyncSession,
    mcp_id: str,
    include_integration: bool = True,
) -> ValidationReport:
    """Run all validation rules against an MCP and return a structured report."""
    mcp = await db.get(MCPDefinition, mcp_id)
    if not mcp:
        raise ValueError(f"MCP {mcp_id} not found")

    report = ValidationReport(mcp_id=mcp_id, valid=True, score=100, categories_checked=[])
    all_findings: list[ValidationFinding] = []

    # 1. Structural
    report.categories_checked.append("structural")
    all_findings.extend(_check_structural(mcp))

    # 2. Governance
    report.categories_checked.append("governance")
    all_findings.extend(_check_governance(mcp))

    # 3. Runtime
    report.categories_checked.append("runtime")
    all_findings.extend(_check_runtime(mcp))

    # 4. Contracts
    report.categories_checked.append("contract")
    all_findings.extend(_check_contracts(mcp))

    # 5. Integration (optional — can be slow)
    if include_integration:
        report.categories_checked.append("integration")
        integration_findings, latency = await _check_integration(mcp)
        all_findings.extend(integration_findings)
        report.integration_tested = True
        report.integration_latency_ms = latency

    # Compute scores
    report.findings = all_findings
    report.errors = sum(1 for f in all_findings if f.severity == Severity.ERROR)
    report.warnings = sum(1 for f in all_findings if f.severity == Severity.WARNING)
    report.infos = sum(1 for f in all_findings if f.severity == Severity.INFO)
    report.valid = report.errors == 0

    # Score: start at 100, -15 per error, -5 per warning, -1 per info
    report.score = max(0, 100 - (report.errors * 15) - (report.warnings * 5) - (report.infos * 1))

    return report


# ────────────────────────────────────────────────────────────
# Lifecycle Gate Validation
# ────────────────────────────────────────────────────────────

LIFECYCLE_GATES: dict[str, list[str]] = {
    "tested": ["structural"],                            # Must pass structural to be tested
    "registered": ["structural", "governance"],          # Must pass governance to register
    "active": ["structural", "governance", "runtime", "contract"],  # Full validation for active
}


async def validate_lifecycle_gate(
    db: AsyncSession,
    mcp_id: str,
    target_status: str,
) -> ValidationReport:
    """Validate an MCP against the rules required for a lifecycle transition.

    Returns a report. If report.valid is False, the transition should be blocked.
    """
    required_categories = LIFECYCLE_GATES.get(target_status)
    if required_categories is None:
        # No gate for this transition
        report = ValidationReport(mcp_id=mcp_id, valid=True, score=100)
        return report

    # Run full validation
    include_integration = "integration" in required_categories
    report = await validate_mcp(db, mcp_id, include_integration=include_integration)

    # Filter findings to only required categories
    gate_findings = [f for f in report.findings if f.category in required_categories]
    gate_errors = sum(1 for f in gate_findings if f.severity == Severity.ERROR)

    report.findings = gate_findings
    report.errors = gate_errors
    report.warnings = sum(1 for f in gate_findings if f.severity == Severity.WARNING)
    report.infos = sum(1 for f in gate_findings if f.severity == Severity.INFO)
    report.valid = gate_errors == 0
    report.score = max(0, 100 - (gate_errors * 15) - (report.warnings * 5) - (report.infos * 1))
    report.categories_checked = required_categories

    return report
