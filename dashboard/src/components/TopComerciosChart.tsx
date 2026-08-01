import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ComercioItem } from "../api";
import { formatMonto, TIPO_COLOR, TIPO_LABEL } from "../api";

interface Props {
  data: ComercioItem[];
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const item: ComercioItem = payload[0].payload;
  return (
    <div
      className="rounded-lg p-3 text-sm shadow-lg"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <p className="mb-1 font-medium" style={{ color: "var(--text-primary)" }}>
        {item.comercio}
      </p>
      <p style={{ color: "var(--text-secondary)" }}>{TIPO_LABEL[item.tipo]}</p>
      <p className="tabular mt-1 font-semibold" style={{ color: "var(--text-primary)" }}>
        {formatMonto(item.total)} · {item.movimientos} mov.
      </p>
    </div>
  );
}

export function TopComerciosChart({ data }: Props) {
  const rows = [...data].sort((a, b) => a.total - b.total); // Recharts vertical layout dibuja de abajo hacia arriba

  return (
    <div
      className="rounded-xl p-5"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <h2 className="mb-4 text-base font-semibold" style={{ color: "var(--text-primary)" }}>
        Top comercios
      </h2>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={rows} layout="vertical" margin={{ left: 8 }}>
          <CartesianGrid horizontal={false} stroke="var(--gridline)" />
          <XAxis
            type="number"
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `S/${v}`}
          />
          <YAxis
            type="category"
            dataKey="comercio"
            tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={150}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--gridline)", opacity: 0.4 }} />
          <Bar dataKey="total" radius={[0, 4, 4, 0]} maxBarSize={18}>
            {rows.map((row) => (
              <Cell key={row.comercio} fill={TIPO_COLOR[row.tipo]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
