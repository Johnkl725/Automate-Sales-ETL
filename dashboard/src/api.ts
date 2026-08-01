export interface ResumenGeneral {
  totalGastado: number;
  cantidadMovimientos: number;
  promedioMovimiento: number;
  gastoMesActual: number;
  gastoMesAnterior: number;
  variacionPct: number | null;
  rango: { desde: string | null; hasta: string | null };
}

export interface ResumenMensualItem {
  mes: string;
  tipo: "consumo_tarjeta" | "pago_servicio";
  total: number;
  movimientos: number;
}

export interface ComercioItem {
  comercio: string;
  tipo: "consumo_tarjeta" | "pago_servicio";
  total: number;
  movimientos: number;
}

export interface MovimientoItem {
  messageId: string;
  fechaConsumo: string;
  monto: number;
  moneda: string;
  tipo: "consumo_tarjeta" | "pago_servicio";
  comercio: string | null;
}

export interface MovimientosFiltros {
  tipo?: string;
  comercio?: string;
  page: number;
  pageSize: number;
}

const BASE = "/api/gastos";

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  resumenGeneral: () => getJson<ResumenGeneral>(`${BASE}/resumen-general`),

  resumenMensual: (meses = 12) =>
    getJson<ResumenMensualItem[]>(`${BASE}/resumen-mensual?meses=${meses}`),

  topComercios: (limit = 8) =>
    getJson<ComercioItem[]>(`${BASE}/top-comercios?limit=${limit}`),

  movimientos: (filtros: MovimientosFiltros) => {
    const params = new URLSearchParams({
      page: String(filtros.page),
      pageSize: String(filtros.pageSize),
    });
    if (filtros.tipo) params.set("tipo", filtros.tipo);
    if (filtros.comercio) params.set("comercio", filtros.comercio);
    return getJson<{ items: MovimientoItem[]; total: number }>(
      `${BASE}/movimientos?${params.toString()}`,
    );
  },
};

export const TIPO_LABEL: Record<string, string> = {
  consumo_tarjeta: "Consumo con tarjeta",
  pago_servicio: "Pago de servicio",
};

export const TIPO_COLOR: Record<string, string> = {
  consumo_tarjeta: "var(--series-consumo)",
  pago_servicio: "var(--series-pago)",
};

export function formatMonto(monto: number, moneda = "PEN"): string {
  const symbol = moneda === "USD" ? "US$" : "S/";
  return `${symbol} ${monto.toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
