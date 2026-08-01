import { useEffect, useState } from "react";
import { api, formatMonto } from "./api";
import type { ComercioItem, ResumenGeneral, ResumenMensualItem } from "./api";
import { StatTile } from "./components/StatTile";
import { MonthlyChart } from "./components/MonthlyChart";
import { TopComerciosChart } from "./components/TopComerciosChart";
import { MovimientosTable } from "./components/MovimientosTable";

function App() {
  const [resumen, setResumen] = useState<ResumenGeneral | null>(null);
  const [mensual, setMensual] = useState<ResumenMensualItem[]>([]);
  const [comercios, setComercios] = useState<ComercioItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.resumenGeneral(), api.resumenMensual(12), api.topComercios(8)])
      .then(([r, m, c]) => {
        setResumen(r);
        setMensual(m);
        setComercios(c);
      })
      .catch(() => setError("No se pudo conectar con la API. ¿Esta corriendo en :3000?"));
  }, []);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center" style={{ color: "var(--bad)" }}>
        {error}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Mis gastos BCP
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
          {resumen?.rango.desde && resumen?.rango.hasta
            ? `Desde ${resumen.rango.desde.slice(0, 10)} hasta ${resumen.rango.hasta.slice(0, 10)}`
            : "Cargando..."}
        </p>
      </header>

      <section className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Total gastado"
          value={resumen ? formatMonto(resumen.totalGastado) : "—"}
        />
        <StatTile
          label="Movimientos"
          value={resumen ? String(resumen.cantidadMovimientos) : "—"}
        />
        <StatTile
          label="Promedio por movimiento"
          value={resumen ? formatMonto(resumen.promedioMovimiento) : "—"}
        />
        <StatTile
          label="Gasto del mes"
          value={resumen ? formatMonto(resumen.gastoMesActual) : "—"}
          delta={
            resumen?.variacionPct != null
              ? {
                  text: `${Math.abs(resumen.variacionPct).toFixed(1)}% vs mes anterior`,
                  direction: resumen.variacionPct >= 0 ? "up" : "down",
                }
              : null
          }
        />
      </section>

      <section className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <MonthlyChart data={mensual} />
        <TopComerciosChart data={comercios} />
      </section>

      <section>
        <MovimientosTable />
      </section>
    </div>
  );
}

export default App;
