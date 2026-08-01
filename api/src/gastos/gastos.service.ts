import { Injectable } from '@nestjs/common';
import { DuckdbService } from './duckdb.service';

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
  tipo: string;
  total: number;
  movimientos: number;
}

export interface ComercioItem {
  comercio: string;
  tipo: string;
  total: number;
  movimientos: number;
}

export interface MovimientoItem {
  messageId: string;
  fechaConsumo: string;
  monto: number;
  moneda: string;
  tipo: string;
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

/** Filtros globales de cabecera: rango de fechas + tipo. Se aplican por
 * igual a los KPIs, la tendencia mensual y el top de comercios, para que
 * las tres vistas siempre cuenten la misma historia. */
export interface GlobalFiltros {
  desde?: string;
  hasta?: string;
  tipo?: string;
}

const TIPOS_VALIDOS = new Set(['consumo_tarjeta', 'pago_servicio']);

function buildWhere(filtros: GlobalFiltros, extra: string[] = []): { clause: string; params: unknown[] } {
  const where: string[] = [...extra];
  const params: unknown[] = [];

  if (filtros.tipo && TIPOS_VALIDOS.has(filtros.tipo)) {
    where.push('tipo = ?');
    params.push(filtros.tipo);
  }
  if (filtros.desde) {
    where.push('fecha_consumo >= ?');
    params.push(filtros.desde);
  }
  if (filtros.hasta) {
    where.push('fecha_consumo <= ?');
    params.push(filtros.hasta);
  }
  return { clause: where.length ? `WHERE ${where.join(' AND ')}` : '', params };
}

@Injectable()
export class GastosService {
  constructor(private readonly db: DuckdbService) {}

  async getResumenGeneral(filtros: GlobalFiltros = {}): Promise<ResumenGeneral> {
    const { clause, params } = buildWhere(filtros);

    const [totales] = await this.db.all<{
      total: number | null;
      movimientos: bigint;
      desde: string | null;
      hasta: string | null;
    }>(
      `SELECT SUM(monto) AS total, COUNT(*) AS movimientos,
              MIN(fecha_consumo)::VARCHAR AS desde, MAX(fecha_consumo)::VARCHAR AS hasta
       FROM gastos ${clause}`,
      params,
    );

    // El comparativo "este mes vs anterior" es una metrica de calendario
    // real (independiente del rango elegido en el filtro), pero respeta el
    // filtro de tipo para que sea coherente con lo que se ve en pantalla.
    const { clause: tipoClause, params: tipoParams } = buildWhere({ tipo: filtros.tipo });
    const [porMes] = await this.db.all<{ total_actual: number | null; total_anterior: number | null }>(
      `SELECT
         SUM(monto) FILTER (WHERE strftime(fecha_consumo, '%Y-%m') = strftime(current_date, '%Y-%m')) AS total_actual,
         SUM(monto) FILTER (WHERE strftime(fecha_consumo, '%Y-%m') = strftime(current_date - INTERVAL 1 MONTH, '%Y-%m')) AS total_anterior
       FROM gastos ${tipoClause}`,
      tipoParams,
    );

    const total = totales.total ?? 0;
    const movimientos = Number(totales.movimientos);
    const gastoMesActual = porMes.total_actual ?? 0;
    const gastoMesAnterior = porMes.total_anterior ?? 0;

    return {
      totalGastado: total,
      cantidadMovimientos: movimientos,
      promedioMovimiento: movimientos > 0 ? total / movimientos : 0,
      gastoMesActual,
      gastoMesAnterior,
      variacionPct:
        gastoMesAnterior > 0 ? ((gastoMesActual - gastoMesAnterior) / gastoMesAnterior) * 100 : null,
      rango: { desde: totales.desde, hasta: totales.hasta },
    };
  }

  async getResumenMensual(meses = 12, filtros: GlobalFiltros = {}): Promise<ResumenMensualItem[]> {
    // Si viene un rango explicito (desde/hasta) desde el filtro de cabecera,
    // manda sobre la ventana relativa de "ultimos N meses".
    const extra = filtros.desde || filtros.hasta ? [] : ['fecha_consumo >= current_date - INTERVAL (?) MONTH'];
    const { clause, params } = buildWhere(filtros, extra);
    const fullParams = extra.length ? [meses, ...params] : params;

    const rows = await this.db.all<{
      mes: string;
      tipo: string;
      total: number;
      movimientos: bigint;
    }>(
      `SELECT strftime(fecha_consumo, '%Y-%m') AS mes, tipo,
              SUM(monto) AS total, COUNT(*) AS movimientos
       FROM gastos ${clause}
       GROUP BY mes, tipo
       ORDER BY mes ASC`,
      fullParams,
    );
    return rows.map((r) => ({ ...r, movimientos: Number(r.movimientos) }));
  }

  /** Años con datos disponibles, para poblar el selector de año/mes de la
   * cabecera. Consulta directa (DISTINCT sobre fecha_consumo) -- no hace
   * falta una tabla de dimension de tiempo para una sola tabla de hechos
   * de este tamaño; DuckDB calcula el año al vuelo sin costo. */
  async getPeriodosDisponibles(): Promise<{ anios: number[] }> {
    const rows = await this.db.all<{ anio: number }>(
      `SELECT DISTINCT EXTRACT(YEAR FROM fecha_consumo)::INT AS anio
       FROM gastos
       ORDER BY anio DESC`,
    );
    return { anios: rows.map((r) => r.anio) };
  }

  async getTopComercios(limit = 10, filtros: GlobalFiltros = {}): Promise<ComercioItem[]> {
    const { clause, params } = buildWhere(filtros, ['comercio IS NOT NULL']);
    const rows = await this.db.all<{
      comercio: string;
      tipo: string;
      total: number;
      movimientos: bigint;
    }>(
      `SELECT comercio, tipo, SUM(monto) AS total, COUNT(*) AS movimientos
       FROM gastos ${clause}
       GROUP BY comercio, tipo
       ORDER BY total DESC
       LIMIT ?`,
      [...params, limit],
    );
    return rows.map((r) => ({ ...r, movimientos: Number(r.movimientos) }));
  }

  async getMovimientos(
    filtros: MovimientosFiltros,
  ): Promise<{ items: MovimientoItem[]; total: number }> {
    const where: string[] = [];
    const params: unknown[] = [];

    if (filtros.tipo && TIPOS_VALIDOS.has(filtros.tipo)) {
      where.push('tipo = ?');
      params.push(filtros.tipo);
    }
    if (filtros.desde) {
      where.push('fecha_consumo >= ?');
      params.push(filtros.desde);
    }
    if (filtros.hasta) {
      where.push('fecha_consumo <= ?');
      params.push(filtros.hasta);
    }
    if (filtros.comercio) {
      where.push('comercio ILIKE ?');
      params.push(`%${filtros.comercio}%`);
    }
    const whereClause = where.length ? `WHERE ${where.join(' AND ')}` : '';

    const [{ total }] = await this.db.all<{ total: bigint }>(
      `SELECT COUNT(*) AS total FROM gastos ${whereClause}`,
      params,
    );

    const offset = (filtros.page - 1) * filtros.pageSize;
    const rows = await this.db.all<{
      message_id: string;
      fecha_consumo: string;
      monto: number;
      moneda: string;
      tipo: string;
      comercio: string | null;
    }>(
      `SELECT message_id, fecha_consumo::VARCHAR AS fecha_consumo, monto, moneda, tipo, comercio
       FROM gastos ${whereClause}
       ORDER BY fecha_consumo DESC
       LIMIT ? OFFSET ?`,
      [...params, filtros.pageSize, offset],
    );

    return {
      items: rows.map((r) => ({
        messageId: r.message_id,
        fechaConsumo: r.fecha_consumo,
        monto: r.monto,
        moneda: r.moneda,
        tipo: r.tipo,
        comercio: r.comercio,
      })),
      total: Number(total),
    };
  }
}
