"use client";

interface ConfirmDangerDialogProps {
  open: boolean;
  title: string;
  description: string;
  targetLabel?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDangerDialog({
  open,
  title,
  description,
  targetLabel,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDangerDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm p-4 md:p-8">
      <div className="max-w-xl mx-auto glass-panel border border-ork-red/40">
        <div className="p-4 border-b border-ork-border">
          <p className="text-xs font-mono uppercase tracking-wider text-ork-red">Danger Zone</p>
          <h3 className="text-lg font-semibold mt-1">{title}</h3>
          <p className="text-sm text-ork-muted mt-2">{description}</p>
          {targetLabel && (
            <p className="mt-3 text-xs font-mono text-ork-cyan bg-ork-bg border border-ork-border rounded px-2 py-1 inline-block">
              {targetLabel}
            </p>
          )}
        </div>

        <div className="p-4 flex items-center justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-border text-ork-muted disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-red/30 text-ork-red bg-ork-red/10 disabled:opacity-50"
          >
            {loading ? "Deleting..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
