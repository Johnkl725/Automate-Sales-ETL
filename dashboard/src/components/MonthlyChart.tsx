import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ResumenMensualItem } from "../api";
import { formatMonto, TIPO_COLOR, TIPO_LABEL } from "../api";
import { TipoLegend } from "./TipoLegend";

interface Props {
  data: ResumenMensualItem[];
}

interface Row {
  mes: string;
  consumo_tarjeta: number;
  pago_servicio: number;
}

function pivot(data: ResumenMensualItem[]): Row[] {
  const byMes = new Map<string, Row>();
  for (const item of data) {
    const row = byMes.get(item.mes) ?? { mes: item.mes, consumo_tarjeta: 0, pago_servicio: 0 };
    row[item.tipo] = item.total;
    byMes.set(item.mes, row);
  }
  return [...byMes.values()].sort((a, b) => a.mes.localeCompare(b.mes));
}

function mesLabel(mes: string): string {
  const [y, m] = mes.split("-");
  const nombre = new Date(Number(y), Number(m) - 1, 1).toLocaleDateString("es-PE", {
    month: "short",
  });
  return nombre.replace(".", "");
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((sum: number, p: any) => sum + (p.value ?? 0), 0);
  return (
    <div
      className="rounded-lg p-3 text-sm shadow-lg"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <p className="mb-1.5 font-medium" style={{ color: "var(--text-primary)" }}>
        {label}
      </p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-6">
          <span className="flex items-center gap-1.5" style={{ color: "var(--text-secondary)" }}>
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: TIPO_COLOR[p.dataKey] }}
            />
            {TIPO_LABEL[p.dataKey]}
          </span>
          <span className="tabular font-medium" style={{ color: "var(--text-primary)" }}>
            {formatMonto(p.value ?? 0)}
          </span>
        </div>
      ))}
      <div
        className="mt-1.5 flex items-center justify-between gap-6 border-t pt-1.5"
        style={{ borderColor: "var(--border)" }}
      >
        <span style={{ color: "var(--text-muted)" }}>Total</span>
        <span className="tabular font-semibold" style={{ color: "var(--text-primary)" }}>
          {formatMonto(total)}
        </span>
      </div>
    </div>
  );
}

export function MonthlyChart({ data }: Props) {
  const rows = pivot(data);

  return (
    <div
      className="rounded-xl p-5"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          Gasto mensual
        </h2>
        <TipoLegend />
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={rows} barCategoryGap={12}>
          <CartesianGrid vertical={false} stroke="var(--gridline)" />
          <XAxis
            dataKey="mes"
            tickFormatter={mesLabel}
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            axisLine={{ stroke: "var(--axis)" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={48}
            tickFormatter={(v) => `S/${v}`}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--gridline)", opacity: 0.4 }} />
          <Bar
            dataKey="consumo_tarjeta"
            stackId="gasto"
            fill={TIPO_COLOR.consumo_tarjeta}
            maxBarSize={24}
          />
          <Bar
            dataKey="pago_servicio"
            stackId="gasto"
            fill={TIPO_COLOR.pago_servicio}
            radius={[4, 4, 0, 0]}
            maxBarSize={24}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
