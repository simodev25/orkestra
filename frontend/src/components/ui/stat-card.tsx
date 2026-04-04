interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "cyan" | "green" | "amber" | "red" | "purple";
}

const accents = {
  cyan: "border-ork-cyan/20 text-ork-cyan",
  green: "border-ork-green/20 text-ork-green",
  amber: "border-ork-amber/20 text-ork-amber",
  red: "border-ork-red/20 text-ork-red",
  purple: "border-ork-purple/20 text-ork-purple",
};

export function StatCard({ label, value, sub, accent = "cyan" }: StatCardProps) {
  return (
    <div className={`glass-panel p-4 border-l-2 ${accents[accent]}`}>
      <p className="data-label mb-1">{label}</p>
      <p className={`stat-value ${accents[accent].split(" ")[1]}`}>{value}</p>
      {sub && <p className="text-xs text-ork-muted mt-1 font-mono">{sub}</p>}
    </div>
  );
}
