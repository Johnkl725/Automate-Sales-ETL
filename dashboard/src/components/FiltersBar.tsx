import { useEffect, useState } from "react";
import { api, TIPO_LABEL } from "../api";

export type RangoPreset = "todo" | "30d" | "90d" | "6m" | "mes";

export interface Filtros {
  preset: RangoPreset;
  tipo: string;
  /** Año/mes seleccionados explícitamente ("" = sin elegir). Cuando hay un
   * año elegido, este filtro manda sobre el preset de rango relativo. */
  anio: string;
  mes: string;
}

export const FILTROS_INICIALES: Filtros = { preset: "todo", tipo: "", anio: "", mes: "" };

const PRESETS: { value: RangoPreset; label: string }[] = [
  { value: "todo", label: "Todo el historial" },
  { value: "30d", label: "Últimos 30 días" },
  { value: "90d", label: "Últimos 90 días" },
  { value: "6m", label: "Últimos 6 meses" },
  { value: "mes", label: "Este mes" },
];

const MESES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

function presetToRango(preset: RangoPreset): { desde?: string; hasta?: string } {
  const hoy = new Date();
  const iso = (d: Date) => d.toISOString().slice(0, 10);

  switch (preset) {
    case "30d": {
      const desde = new Date(hoy);
      desde.setDate(desde.getDate() - 30);
      return { desde: iso(desde) };
    }
    case "90d": {
      const desde = new Date(hoy);
      desde.setDate(desde.getDate() - 90);
      return { desde: iso(desde) };
    }
    case "6m": {
      const desde = new Date(hoy);
      desde.setMonth(desde.getMonth() - 6);
      return { desde: iso(desde) };
    }
    case "mes": {
      const desde = new Date(hoy.getFullYear(), hoy.getMonth(), 1);
      return { desde: iso(desde) };
    }
    case "todo":
    default:
      return {};
  }
}

function anioMesToRango(anio: string, mes: string): { desde?: string; hasta?: string } {
  if (!anio) return {};
  const y = Number(anio);
  if (!mes) {
    return { desde: `${y}-01-01`, hasta: `${y}-12-31` };
  }
  const m = Number(mes);
  const ultimoDia = new Date(y, m, 0).getDate();
  return { desde: `${y}-${String(m).padStart(2, "0")}-01`, hasta: `${y}-${String(m).padStart(2, "0")}-${ultimoDia}` };
}

/** Traduce los filtros de cabecera a { desde, hasta } para la API. El
 * selector de año/mes tiene prioridad sobre el preset de rango relativo. */
export function filtrosToRango(filtros: Filtros): { desde?: string; hasta?: string } {
  return filtros.anio ? anioMesToRango(filtros.anio, filtros.mes) : presetToRango(filtros.preset);
}

const selectStyle = {
  background: "var(--page)",
  border: "1px solid var(--border)",
  color: "var(--text-primary)",
};

interface FiltersBarProps {
  filtros: Filtros;
  onChange: (filtros: Filtros) => void;
  onMenuClick: () => void;
}

export function FiltersBar({ filtros, onChange, onMenuClick }: FiltersBarProps) {
  const [anios, setAnios] = useState<number[]>([]);

  useEffect(() => {
    api.periodos().then((r) => setAnios(r.anios)).catch(() => setAnios([]));
  }, []);

  const anioMesActivo = Boolean(filtros.anio);
  const hayFiltrosActivos = filtros.preset !== "todo" || filtros.tipo || filtros.anio;

  return (
    <div
      className="sticky top-0 z-20 flex flex-wrap items-center gap-3 px-4 py-3 backdrop-blur sm:px-6 lg:px-8"
      style={{ background: "color-mix(in srgb, var(--page) 92%, transparent)", borderBottom: "1px solid var(--border)" }}
    >
      <button
        onClick={onMenuClick}
        className="rounded-md p-1.5 lg:hidden"
        style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}
        aria-label="Abrir menú"
      >
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
      </button>

      <span className="text-sm font-medium" style={{ color: "var(--text-muted)" }}>
        Filtros:
      </span>

      <select
        value={filtros.preset}
        onChange={(e) => onChange({ ...filtros, preset: e.target.value as RangoPreset, anio: "", mes: "" })}
        disabled={anioMesActivo}
        className="rounded-md px-3 py-1.5 text-sm outline-none disabled:opacity-40"
        style={selectStyle}
        title={anioMesActivo ? "Desactivado mientras haya un año/mes elegido" : undefined}
      >
        {PRESETS.map((p) => (
          <option key={p.value} value={p.value}>
            {p.label}
          </option>
        ))}
      </select>

      <span className="hidden text-xs sm:inline" style={{ color: "var(--text-muted)" }}>
        o
      </span>

      <select
        value={filtros.anio}
        onChange={(e) => onChange({ ...filtros, anio: e.target.value, mes: e.target.value ? filtros.mes : "" })}
        className="rounded-md px-3 py-1.5 text-sm outline-none"
        style={selectStyle}
      >
        <option value="">Año</option>
        {anios.map((a) => (
          <option key={a} value={a}>
            {a}
          </option>
        ))}
      </select>

      <select
        value={filtros.mes}
        onChange={(e) => onChange({ ...filtros, mes: e.target.value })}
        disabled={!filtros.anio}
        className="rounded-md px-3 py-1.5 text-sm outline-none disabled:opacity-40"
        style={selectStyle}
      >
        <option value="">Todo el año</option>
        {MESES.map((nombre, i) => (
          <option key={nombre} value={i + 1}>
            {nombre}
          </option>
        ))}
      </select>

      <select
        value={filtros.tipo}
        onChange={(e) => onChange({ ...filtros, tipo: e.target.value })}
        className="rounded-md px-3 py-1.5 text-sm outline-none"
        style={selectStyle}
      >
        <option value="">Todos los tipos</option>
        <option value="consumo_tarjeta">{TIPO_LABEL.consumo_tarjeta}</option>
        <option value="pago_servicio">{TIPO_LABEL.pago_servicio}</option>
      </select>

      {hayFiltrosActivos && (
        <button
          onClick={() => onChange({ preset: "todo", tipo: "", anio: "", mes: "" })}
          className="text-sm font-medium underline-offset-2 hover:underline"
          style={{ color: "var(--series-consumo)" }}
        >
          Limpiar filtros
        </button>
      )}
    </div>
  );
}
