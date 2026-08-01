import { Module } from '@nestjs/common';
import { GastosController } from './gastos.controller';
import { GastosService } from './gastos.service';
import { DuckdbService } from './duckdb.service';

@Module({
  controllers: [GastosController],
  providers: [DuckdbService, GastosService],
})
export class GastosModule {}
