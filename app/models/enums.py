"""Orkestra domain enumerations."""

import enum


class RequestStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONVERTED_TO_CASE = "converted_to_case"
    CANCELLED = "cancelled"


class CaseStatus(str, enum.Enum):
    CREATED = "created"
    READY_FOR_PLANNING = "ready_for_planning"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class PlanStatus(str, enum.Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    ADJUSTED_BY_CONTROL = "adjusted_by_control"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"


class RunStatus(str, enum.Enum):
    CREATED = "created"
    PLANNED = "planned"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    HOLD = "hold"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunNodeStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING_DEPENDENCY = "waiting_dependency"
    WAITING_REVIEW = "waiting_review"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    FAILED = "failed"


class RunNodeType(str, enum.Enum):
    SUBAGENT = "subagent"
    APPROVAL_GATE = "approval_gate"
    SYNC_POINT = "sync_point"
    CONTROL_GATE = "control_gate"


class SubagentInvocationStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"


class MCPInvocationStatus(str, enum.Enum):
    REQUESTED = "requested"
    ALLOWED = "allowed"
    DENIED = "denied"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"


class ControlDecisionScope(str, enum.Enum):
    PLAN = "plan"
    AGENT = "agent"
    MCP = "mcp"
    RELEASE = "release"
    APPROVAL = "approval"


class ControlDecisionType(str, enum.Enum):
    ALLOW = "allow"
    DENY = "deny"
    HOLD = "hold"
    REVIEW_REQUIRED = "review_required"
    ADJUST = "adjust"


class ApprovalStatus(str, enum.Enum):
    REQUESTED = "requested"
    ASSIGNED = "assigned"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REFINE_REQUIRED = "refine_required"
    CANCELLED = "cancelled"


class ReplayBundleStatus(str, enum.Enum):
    NOT_GENERATED = "not_generated"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class AgentStatus(str, enum.Enum):
    DRAFT = "draft"
    DESIGNED = "designed"
    TESTED = "tested"
    REGISTERED = "registered"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class MCPStatus(str, enum.Enum):
    DRAFT = "draft"
    TESTED = "tested"
    REGISTERED = "registered"
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class MCPEffectType(str, enum.Enum):
    READ = "read"
    SEARCH = "search"
    COMPUTE = "compute"
    GENERATE = "generate"
    VALIDATE = "validate"
    WRITE = "write"
    ACT = "act"


class Criticality(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CostProfile(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VARIABLE = "variable"


class InputMode(str, enum.Enum):
    MANUAL = "manual"
    API = "api"
    EVENT = "event"


class ExecutionMode(str, enum.Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    MIXED = "mixed"
    CONDITIONAL = "conditional"


class TestRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class TestVerdict(str, enum.Enum):
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"


class EventType(str, enum.Enum):
    RUN_CREATED = "run_created"
    ORCHESTRATOR_STARTED = "orchestrator_started"
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"
    HANDOFF_STARTED = "handoff_started"
    HANDOFF_COMPLETED = "handoff_completed"
    RUN_STARTED = "run_started"
    AGENT_ITERATION_STARTED = "agent_iteration_started"
    AGENT_ITERATION_COMPLETED = "agent_iteration_completed"
    LLM_REQUEST_STARTED = "llm_request_started"
    LLM_REQUEST_COMPLETED = "llm_request_completed"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_CALL_FAILED = "tool_call_failed"
    MCP_SESSION_CONNECTED = "mcp_session_connected"
    MCP_SESSION_FAILED = "mcp_session_failed"
    ASSERTION_PHASE_STARTED = "assertion_phase_started"
    ASSERTION_PASSED = "assertion_passed"
    ASSERTION_FAILED = "assertion_failed"
    DIAGNOSTIC_PHASE_STARTED = "diagnostic_phase_started"
    DIAGNOSTIC_GENERATED = "diagnostic_generated"
    REPORT_PHASE_STARTED = "report_phase_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_TIMEOUT = "run_timeout"


class AssertionType(str, enum.Enum):
    TOOL_CALLED = "tool_called"
    TOOL_NOT_CALLED = "tool_not_called"
    OUTPUT_FIELD_EXISTS = "output_field_exists"
    OUTPUT_SCHEMA_MATCHES = "output_schema_matches"
    MAX_DURATION_MS = "max_duration_ms"
    MAX_ITERATIONS = "max_iterations"
    FINAL_STATUS_IS = "final_status_is"
    NO_TOOL_FAILURES = "no_tool_failures"


class DiagnosticCode(str, enum.Enum):
    EXPECTED_TOOL_NOT_USED = "expected_tool_not_used"
    TOOL_FAILURE_DETECTED = "tool_failure_detected"
    RUN_TIMED_OUT = "run_timed_out"
    OUTPUT_SCHEMA_INVALID = "output_schema_invalid"
    EXCESSIVE_ITERATIONS = "excessive_iterations"
    SLOW_FINAL_SYNTHESIS = "slow_final_synthesis"
    NO_PROGRESS_DETECTED = "no_progress_detected"


class Severity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class FamilyStatus(str, enum.Enum):
    active = "active"
    archived = "archived"
    deprecated = "deprecated"


class SkillStatus(str, enum.Enum):
    active = "active"
    archived = "archived"
    deprecated = "deprecated"
