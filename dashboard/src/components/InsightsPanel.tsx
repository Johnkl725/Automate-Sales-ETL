import type { ReactNode } from "react";
import type { ComercioItem, ResumenGeneral, ResumenMensualItem } from "../api";
import { formatMonto, TIPO_COLOR, TIPO_LABEL } from "../api";

interface Props {
  resumen: ResumenGeneral | null;
  mensual: ResumenMensualItem[];
  comercios: ComercioItem[];
}

function diasEnRango(desde: string | null, hasta: string | null): number {
  if (!desde || !hasta) return 0;
  const d = new Date(desde.slice(0, 10));
  const h = new Date(hasta.slice(0, 10));
  const dias = Math.round((h.getTime() - d.getTime()) / 86_400_000) + 1;
  return Math.max(dias, 1);
}

/** Barra de proporcion de un solo segmento por tipo -- codificacion
 * secundaria (ancho + etiqueta numerica), nunca solo color, siguiendo la
 * regla de "texto nunca lleva el color de la serie". */
function ProportionBar({ consumoPct, pagoPct }: { consumoPct: number; pagoPct: number }) {
  return (
    <div>
      <div className="flex h-2.5 w-full overflow-hidden rounded-full" style={{ background: "var(--gridline)" }}>
        <div style={{ width: `${consumoPct}%`, background: TIPO_COLOR.consumo_tarjeta }} />
        <div style={{ width: `${pagoPct}%`, background: TIPO_COLOR.pago_servicio }} />
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <span className="flex items-center gap-1.5" style={{ color: "var(--text-secondary)" }}>
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: TIPO_COLOR.consumo_tarjeta }} />
          {TIPO_LABEL.consumo_tarjeta} · <span className="tabular font-medium" style={{ color: "var(--text-primary)" }}>{consumoPct.toFixed(0)}%</span>
        </span>
        <span className="flex items-center gap-1.5" style={{ color: "var(--text-secondary)" }}>
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: TIPO_COLOR.pago_servicio }} />
          {TIPO_LABEL.pago_servicio} · <span className="tabular font-medium" style={{ color: "var(--text-primary)" }}>{pagoPct.toFixed(0)}%</span>
        </span>
      </div>
    </div>
  );
}

function InsightRow({ icon, children }: { icon: string; children: ReactNode }) {
  return (
    <li className="flex items-start gap-2.5 text-sm" style={{ color: "var(--text-secondary)" }}>
      <span className="mt-0.5 shrink-0" aria-hidden>
        {icon}
      </span>
      <span>{children}</span>
    </li>
  );
}

export function InsightsPanel({ resumen, mensual, comercios }: Props) {
  if (!resumen) return null;

  const totalConsumo = mensual
    .filter((m) => m.tipo === "consumo_tarjeta")
    .reduce((sum, m) => sum + m.total, 0);
  const totalPago = mensual.filter((m) => m.tipo === "pago_servicio").reduce((sum, m) => sum + m.total, 0);
  const totalTipos = totalConsumo + totalPago;
  const consumoPct = totalTipos > 0 ? (totalConsumo / totalTipos) * 100 : 0;
  const pagoPct = totalTipos > 0 ? (totalPago / totalTipos) * 100 : 0;

  const dias = diasEnRango(resumen.rango.desde, resumen.rango.hasta);
  const promedioDiario = dias > 0 ? resumen.totalGastado / dias : 0;

  const topComercio = comercios[0];

  return (
    <div
      className="grid grid-cols-1 gap-5 rounded-xl p-5 sm:grid-cols-2"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <div>
        <h3 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Hallazgos del período
        </h3>
        <ul className="space-y-2.5">
          {topComercio && (
            <InsightRow icon="🏆">
              Tu mayor gasto es en{" "}
              <span className="font-medium" style={{ color: "var(--text-primary)" }}>
                {topComercio.comercio}
              </span>
              , con {formatMonto(topComercio.total)} en {topComercio.movimientos} movimiento
              {topComercio.movimientos === 1 ? "" : "s"}.
            </InsightRow>
          )}
          <InsightRow icon="📊">
            Gasto diario promedio de{" "}
            <span className="font-medium" style={{ color: "var(--text-primary)" }}>
              {formatMonto(promedioDiario)}
            </span>{" "}
            en los últimos {dias} día{dias === 1 ? "" : "s"}.
          </InsightRow>
          {resumen.variacionPct != null && (
            <InsightRow icon={resumen.variacionPct >= 0 ? "📈" : "📉"}>
              El gasto de este mes{" "}
              <span
                className="font-medium"
                style={{ color: resumen.variacionPct >= 0 ? "var(--bad)" : "var(--good)" }}
              >
                {resumen.variacionPct >= 0 ? "subió" : "bajó"} {Math.abs(resumen.variacionPct).toFixed(1)}%
              </span>{" "}
              respecto al mes anterior.
            </InsightRow>
          )}
        </ul>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Distribución por tipo
        </h3>
        <ProportionBar consumoPct={consumoPct} pagoPct={pagoPct} />
      </div>
    </div>
  );
}
