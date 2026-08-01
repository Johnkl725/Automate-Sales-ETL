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

const TIPOS_VALIDOS = new Set(['consumo_tarjeta', 'pago_servicio']);

@Injectable()
export class GastosService {
  constructor(private readonly db: DuckdbService) {}

  async getResumenGeneral(): Promise<ResumenGeneral> {
    const [totales] = await this.db.all<{
      total: number | null;
      movimientos: bigint;
      desde: string | null;
      hasta: string | null;
    }>(
      `SELECT SUM(monto) AS total, COUNT(*) AS movimientos,
              MIN(fecha_consumo)::VARCHAR AS desde, MAX(fecha_consumo)::VARCHAR AS hasta
       FROM gastos`,
    );

    const [porMes] = await this.db.all<{ total_actual: number | null; total_anterior: number | null }>(
      `SELECT
         SUM(monto) FILTER (WHERE strftime(fecha_consumo, '%Y-%m') = strftime(current_date, '%Y-%m')) AS total_actual,
         SUM(monto) FILTER (WHERE strftime(fecha_consumo, '%Y-%m') = strftime(current_date - INTERVAL 1 MONTH, '%Y-%m')) AS total_anterior
       FROM gastos`,
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

  async getResumenMensual(meses = 12): Promise<ResumenMensualItem[]> {
    const rows = await this.db.all<{
      mes: string;
      tipo: string;
      total: number;
      movimientos: bigint;
    }>(
      `SELECT strftime(fecha_consumo, '%Y-%m') AS mes, tipo,
              SUM(monto) AS total, COUNT(*) AS movimientos
       FROM gastos
       WHERE fecha_consumo >= current_date - INTERVAL (?) MONTH
       GROUP BY mes, tipo
       ORDER BY mes ASC`,
      [meses],
    );
    return rows.map((r) => ({ ...r, movimientos: Number(r.movimientos) }));
  }

  async getTopComercios(limit = 10): Promise<ComercioItem[]> {
    const rows = await this.db.all<{
      comercio: string;
      tipo: string;
      total: number;
      movimientos: bigint;
    }>(
      `SELECT comercio, tipo, SUM(monto) AS total, COUNT(*) AS movimientos
       FROM gastos
       WHERE comercio IS NOT NULL
       GROUP BY comercio, tipo
       ORDER BY total DESC
       LIMIT ?`,
      [limit],
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
