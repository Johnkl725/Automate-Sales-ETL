import { useEffect, useState } from "react";
import { api, formatMonto, TIPO_COLOR, TIPO_LABEL } from "../api";
import type { MovimientoItem } from "../api";

const PAGE_SIZE = 10;

function fechaLabel(fecha: string): string {
  return new Date(fecha.replace(" ", "T")).toLocaleDateString("es-PE", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

interface Props {
  /** Filtro de tipo controlado desde la cabecera del dashboard, para que la
   * tabla siempre este en sincronia con los KPIs y los graficos. */
  tipoGlobal: string;
}

export function MovimientosTable({ tipoGlobal }: Props) {
  const [items, setItems] = useState<MovimientoItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [comercio, setComercio] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setPage(1);
  }, [tipoGlobal]);

  useEffect(() => {
    setLoading(true);
    const handle = setTimeout(() => {
      api
        .movimientos({ page, pageSize: PAGE_SIZE, tipo: tipoGlobal || undefined, comercio: comercio || undefined })
        .then((res) => {
          setItems(res.items);
          setTotal(res.total);
        })
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(handle);
  }, [page, tipoGlobal, comercio]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div
      className="rounded-xl p-5"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          Movimientos
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <input
            placeholder="Buscar comercio..."
            value={comercio}
            onChange={(e) => {
              setPage(1);
              setComercio(e.target.value);
            }}
            className="rounded-md px-3 py-1.5 text-sm outline-none"
            style={{
              background: "var(--page)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th className="py-2 text-left font-medium" style={{ color: "var(--text-muted)" }}>
                Fecha
              </th>
              <th className="py-2 text-left font-medium" style={{ color: "var(--text-muted)" }}>
                Comercio
              </th>
              <th className="py-2 text-left font-medium" style={{ color: "var(--text-muted)" }}>
                Tipo
              </th>
              <th className="py-2 text-right font-medium" style={{ color: "var(--text-muted)" }}>
                Monto
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.messageId} style={{ borderBottom: "1px solid var(--border)" }}>
                <td className="tabular py-2" style={{ color: "var(--text-secondary)" }}>
                  {fechaLabel(item.fechaConsumo)}
                </td>
                <td className="py-2" style={{ color: "var(--text-primary)" }}>
                  {item.comercio ?? "—"}
                </td>
                <td className="py-2">
                  <span className="inline-flex items-center gap-1.5" style={{ color: "var(--text-secondary)" }}>
                    <span
                      className="inline-block h-2 w-2 rounded-full"
                      style={{ background: TIPO_COLOR[item.tipo] }}
                    />
                    {TIPO_LABEL[item.tipo]}
                  </span>
                </td>
                <td
                  className="tabular py-2 text-right font-medium"
                  style={{ color: "var(--text-primary)" }}
                >
                  {formatMonto(item.monto, item.moneda)}
                </td>
              </tr>
            ))}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={4} className="py-6 text-center" style={{ color: "var(--text-muted)" }}>
                  Sin movimientos para este filtro.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between text-sm">
        <span style={{ color: "var(--text-muted)" }}>
          {total} movimiento{total === 1 ? "" : "s"}
        </span>
        <div className="flex items-center gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-md px-2.5 py-1 disabled:opacity-40"
            style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}
          >
            Anterior
          </button>
          <span className="tabular" style={{ color: "var(--text-muted)" }}>
            {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-md px-2.5 py-1 disabled:opacity-40"
            style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}
          >
            Siguiente
          </button>
        </div>
      </div>
    </div>
  );
}
