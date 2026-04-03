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
