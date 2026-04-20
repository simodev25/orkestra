// Mapping statut → variante badge du template
const STATUS_VARIANT: Record<string, string> = {
  // Runs
  running:       "running",
  completed:     "completed",
  failed:        "failed",
  blocked:       "blocked",
  cancelled:     "cancelled",
  planned:       "planned",
  pending:       "pending",
  ready:         "tested",
  hold:          "pending",
  waiting_review:"pending",
  // Requests/cases
  draft:         "draft",
  designed:      "designed",
  submitted:     "tested",
  ready_for_planning: "designed",
  planning:      "designed",
  // Agent/MCP lifecycle
  active:        "active",
  deprecated:    "deprecated",
  disabled:      "disabled",
  degraded:      "degraded",
  tested:        "tested",
  registered:    "registered",
  archived:      "archived",
  restricted:    "pending",
  hidden:        "archived",
  healthy:       "healthy",
  warning:       "warning",
  failing:       "failed",
  published:     "active",
  // Control
  allow:         "allow",
  deny:          "deny",
  review_required: "pending",
  adjust:        "planned",
  // Approvals
  requested:     "pending",
  assigned:      "tested",
  approved:      "approved",
  rejected:      "rejected",
  refine_required: "pending",
  validated:     "active",
  not_tested:    "not_tested",
  passed:        "passed",
  passed_with_warnings: "passed_with_warnings",
  partial:       "pending",
};

export function StatusBadge({ status }: { status: string }) {
  const variant = STATUS_VARIANT[status] || "draft";
  return (
    <span
      role="status"
      aria-label={`Status: ${status.replace(/_/g, " ")}`}
      className={`badge badge--${variant}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
