"""Post-LLM output validation -- checks forbidden effects and output structure."""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    valid: bool
    violations: list[str] = field(default_factory=list)


# Keyword patterns that indicate a forbidden effect was performed
EFFECT_PATTERNS: dict[str, list[str]] = {
    "publish": ["published", "i have published", "sent to production", "deployed"],
    "approve": ["i approve", "approved the", "giving approval", "hereby approve"],
    "external_act": ["sent email", "posted to", "called external api", "notified"],
    "final_decision": ["final decision is", "i have decided", "decision made"],
    "external_act_without_authorization": ["sent email", "posted to", "called external"],
    "unauthorized_external_act": ["sent email", "posted to", "called external"],
}


def validate_forbidden_effects(
    output: str,
    forbidden_effects: list[str],
) -> ValidationResult:
    """Check if LLM output contains forbidden effect indicators."""
    violations = []
    output_lower = output.lower()

    for effect in forbidden_effects:
        patterns = EFFECT_PATTERNS.get(effect, [])
        for pattern in patterns:
            if pattern in output_lower:
                violations.append(
                    f"Forbidden effect '{effect}' detected: output contains '{pattern}'"
                )
                break  # One violation per effect is enough

    return ValidationResult(valid=len(violations) == 0, violations=violations)


def validate_output_structure(output: str) -> ValidationResult:
    """Basic structural validation of LLM output."""
    violations = []
    if not output or not output.strip():
        violations.append("Output is empty")
    elif len(output.strip()) < 10:
        violations.append("Output is suspiciously short (< 10 chars)")
    return ValidationResult(valid=len(violations) == 0, violations=violations)
