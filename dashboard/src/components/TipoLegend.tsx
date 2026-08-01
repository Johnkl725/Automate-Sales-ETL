import { TIPO_COLOR, TIPO_LABEL } from "../api";

export function TipoLegend() {
  return (
    <div className="flex items-center gap-4 text-sm" style={{ color: "var(--text-secondary)" }}>
      {Object.entries(TIPO_LABEL).map(([tipo, label]) => (
        <span key={tipo} className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ background: TIPO_COLOR[tipo] }}
          />
          {label}
        </span>
      ))}
    </div>
  );
}
