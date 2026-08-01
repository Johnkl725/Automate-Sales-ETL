import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { GastosModule } from './gastos/gastos.module';

@Module({
  imports: [ConfigModule.forRoot({ isGlobal: true }), GastosModule],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
