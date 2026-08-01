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
  desde?: string;
  hasta?: string;
  comercio?: string;
  page: number;
  pageSize: number;
}

/** Filtros de la cabecera del dashboard: rango de fechas + tipo. Se le pasan
 * a los 3 endpoints "de vista general" (KPIs, tendencia, top comercios) para
 * que todos cuenten la misma historia a la vez. */
export interface GlobalFiltros {
  desde?: string;
  hasta?: string;
  tipo?: string;
}

const BASE = "/api/gastos";

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json() as Promise<T>;
}

function withGlobalFiltros(params: URLSearchParams, filtros?: GlobalFiltros) {
  if (filtros?.desde) params.set("desde", filtros.desde);
  if (filtros?.hasta) params.set("hasta", filtros.hasta);
  if (filtros?.tipo) params.set("tipo", filtros.tipo);
  return params;
}

export const api = {
  resumenGeneral: (filtros?: GlobalFiltros) => {
    const params = withGlobalFiltros(new URLSearchParams(), filtros);
    const qs = params.toString();
    return getJson<ResumenGeneral>(`${BASE}/resumen-general${qs ? `?${qs}` : ""}`);
  },

  resumenMensual: (meses = 12, filtros?: GlobalFiltros) => {
    const params = withGlobalFiltros(new URLSearchParams({ meses: String(meses) }), filtros);
    return getJson<ResumenMensualItem[]>(`${BASE}/resumen-mensual?${params.toString()}`);
  },

  periodos: () => getJson<{ anios: number[] }>(`${BASE}/periodos`),

  topComercios: (limit = 8, filtros?: GlobalFiltros) => {
    const params = withGlobalFiltros(new URLSearchParams({ limit: String(limit) }), filtros);
    return getJson<ComercioItem[]>(`${BASE}/top-comercios?${params.toString()}`);
  },

  movimientos: (filtros: MovimientosFiltros) => {
    const params = new URLSearchParams({
      page: String(filtros.page),
      pageSize: String(filtros.pageSize),
    });
    if (filtros.tipo) params.set("tipo", filtros.tipo);
    if (filtros.desde) params.set("desde", filtros.desde);
    if (filtros.hasta) params.set("hasta", filtros.hasta);
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
