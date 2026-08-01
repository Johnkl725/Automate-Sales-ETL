import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as duckdb from 'duckdb';

/**
 * Wrapper delgado sobre el driver de DuckDB (API por callbacks) que expone
 * una interfaz basada en Promises. Se conecta en modo READ_ONLY: este
 * proceso solo lee lo que el pipeline de Python (gastos-etl) ya escribio,
 * nunca escribe.
 *
 * DuckDB toma un lock exclusivo sobre el archivo mientras exista CUALQUIER
 * conexion abierta (incluso read-only) que bloquea a un escritor -- si
 * mantuvieramos una conexion viva durante toda la vida del proceso, el DAG
 * diario de Airflow fallaria con "Permission denied" en cuanto intente
 * escribir mientras el dashboard esta corriendo. Por eso cada query abre y
 * cierra su propia conexion: la ventana de lock dura milisegundos en vez de
 * horas.
 */
@Injectable()
export class DuckdbService {
  private readonly logger = new Logger(DuckdbService.name);

  constructor(private readonly config: ConfigService) {}

  private get dbPath(): string {
    return this.config.get<string>('GASTOS_DUCKDB_PATH', '../data/gastos.duckdb');
  }

  all<T = Record<string, unknown>>(sql: string, params: unknown[] = []): Promise<T[]> {
    return new Promise((resolve, reject) => {
      const db = new duckdb.Database(this.dbPath, { access_mode: 'READ_ONLY' });
      const finish = (err: Error | null, rows: unknown) => {
        db.close();
        if (err) return reject(err);
        resolve(rows as T[]);
      };
      (db.all as (...args: unknown[]) => void)(sql, ...params, finish);
    });
  }
}
