import { Controller, Get, Query } from '@nestjs/common';
import { GastosService } from './gastos.service';

function toIntOr(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? Math.trunc(n) : fallback;
}

@Controller('gastos')
export class GastosController {
  constructor(private readonly gastosService: GastosService) {}

  @Get('resumen-general')
  resumenGeneral() {
    return this.gastosService.getResumenGeneral();
  }

  @Get('resumen-mensual')
  resumenMensual(@Query('meses') meses?: string) {
    return this.gastosService.getResumenMensual(toIntOr(meses, 12));
  }

  @Get('top-comercios')
  topComercios(@Query('limit') limit?: string) {
    return this.gastosService.getTopComercios(toIntOr(limit, 10));
  }

  @Get('movimientos')
  movimientos(
    @Query('tipo') tipo?: string,
    @Query('desde') desde?: string,
    @Query('hasta') hasta?: string,
    @Query('comercio') comercio?: string,
    @Query('page') page?: string,
    @Query('pageSize') pageSize?: string,
  ) {
    return this.gastosService.getMovimientos({
      tipo,
      desde,
      hasta,
      comercio,
      page: toIntOr(page, 1),
      pageSize: Math.min(toIntOr(pageSize, 25), 100),
    });
  }
}
