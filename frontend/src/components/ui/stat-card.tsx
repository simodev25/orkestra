interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "cyan" | "green" | "amber" | "red" | "purple";
  barPercent?: number;
}

export function StatCard({ label, value, sub, accent = "cyan", barPercent }: StatCardProps) {
  return (
    <div className={`stat stat--${accent}`}>
      <div className="stat__label">{label}</div>
      <div className="stat__value">{value}</div>
      {sub && <div className="stat__delta">{sub}</div>}
      {barPercent !== undefined && (
        <div className="stat__bar">
          <span style={{ width: `${Math.min(100, Math.max(0, barPercent))}%` }} />
        </div>
      )}
    </div>
  );
}
