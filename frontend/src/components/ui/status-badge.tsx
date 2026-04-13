const STATUS_COLORS: Record<string, string> = {
  // Run/node statuses
  running: "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/30",
  completed: "bg-ork-green/15 text-ork-green border-ork-green/30",
  failed: "bg-ork-red/15 text-ork-red border-ork-red/30",
  blocked: "bg-ork-red/15 text-ork-red border-ork-red/30",
  cancelled: "bg-ork-dim/20 text-ork-muted border-ork-dim/30",
  planned: "bg-ork-purple/15 text-ork-purple border-ork-purple/30",
  pending: "bg-ork-amber/10 text-ork-amber border-ork-amber/20",
  ready: "bg-ork-cyan/10 text-ork-cyan border-ork-cyan/20",
  hold: "bg-ork-amber/15 text-ork-amber border-ork-amber/30",
  waiting_review: "bg-ork-amber/15 text-ork-amber border-ork-amber/30",
  // Request/case
  draft: "bg-ork-dim/20 text-ork-muted border-ork-dim/30",
  designed: "bg-ork-purple/10 text-ork-purple border-ork-purple/20",
  submitted: "bg-ork-cyan/10 text-ork-cyan border-ork-cyan/20",
  ready_for_planning: "bg-ork-purple/15 text-ork-purple border-ork-purple/30",
  planning: "bg-ork-purple/15 text-ork-purple border-ork-purple/30",
  // Agent/MCP lifecycle
  active: "bg-ork-green/15 text-ork-green border-ork-green/30",
  deprecated: "bg-ork-amber/15 text-ork-amber border-ork-amber/30",
  disabled: "bg-ork-red/10 text-ork-red border-ork-red/20",
  degraded: "bg-ork-amber/15 text-ork-amber border-ork-amber/30",
  tested: "bg-ork-cyan/10 text-ork-cyan border-ork-cyan/20",
  registered: "bg-ork-purple/10 text-ork-purple border-ork-purple/20",
  archived: "bg-ork-dim/20 text-ork-muted border-ork-dim/30",
  restricted: "bg-ork-amber/10 text-ork-amber border-ork-amber/20",
  hidden: "bg-ork-dim/20 text-ork-muted border-ork-dim/30",
  healthy: "bg-ork-green/15 text-ork-green border-ork-green/30",
  warning: "bg-ork-amber/15 text-ork-amber border-ork-amber/30",
  failing: "bg-ork-red/15 text-ork-red border-ork-red/30",
  published: "bg-ork-green/15 text-ork-green border-ork-green/30",
  // Control
  allow: "bg-ork-green/15 text-ork-green border-ork-green/30",
  deny: "bg-ork-red/15 text-ork-red border-ork-red/30",
  review_required: "bg-ork-amber/15 text-ork-amber border-ork-amber/30",
  adjust: "bg-ork-purple/15 text-ork-purple border-ork-purple/30",
  // Approval
  requested: "bg-ork-amber/10 text-ork-amber border-ork-amber/20",
  assigned: "bg-ork-cyan/10 text-ork-cyan border-ork-cyan/20",
  approved: "bg-ork-green/15 text-ork-green border-ork-green/30",
  rejected: "bg-ork-red/15 text-ork-red border-ork-red/30",
  refine_required: "bg-ork-amber/15 text-ork-amber border-ork-amber/30",
  validated: "bg-ork-green/15 text-ork-green border-ork-green/30",
  not_tested: "bg-ork-dim/20 text-ork-muted border-ork-dim/30",
  passed: "bg-ork-green/15 text-ork-green border-ork-green/30",
  passed_with_warnings: "bg-ork-amber/15 text-ork-amber border-ork-amber/30",
  partial: "bg-ork-amber/15 text-ork-amber border-ork-amber/30",
};

const DEFAULT = "bg-ork-dim/20 text-ork-muted border-ork-dim/30";

export function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] || DEFAULT;
  return (
    <span
      role="status"
      aria-label={`Status: ${status.replace(/_/g, " ")}`}
      className={`inline-flex items-center px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded ${colors}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
