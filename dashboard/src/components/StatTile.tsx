interface StatTileProps {
  label: string;
  value: string;
  delta?: { text: string; direction: "up" | "down" } | null;
}

export function StatTile({ label, value, delta }: StatTileProps) {
  return (
    <div
      className="rounded-xl p-5"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <p className="text-sm" style={{ color: "var(--text-muted)" }}>
        {label}
      </p>
      <p className="mt-2 text-3xl font-semibold" style={{ color: "var(--text-primary)" }}>
        {value}
      </p>
      {delta && (
        <p
          className="tabular mt-1 text-sm font-medium"
          style={{ color: delta.direction === "up" ? "var(--bad)" : "var(--good)" }}
        >
          {delta.direction === "up" ? "↑" : "↓"} {delta.text}
        </p>
      )}
    </div>
  );
}
