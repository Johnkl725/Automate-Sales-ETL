import { useEffect, useRef, useState } from "react";
import { api, formatMonto } from "./api";
import type { ComercioItem, ResumenGeneral, ResumenMensualItem } from "./api";
import { StatTile } from "./components/StatTile";
import { MonthlyChart } from "./components/MonthlyChart";
import { TopComerciosChart } from "./components/TopComerciosChart";
import { MovimientosTable } from "./components/MovimientosTable";
import { InsightsPanel } from "./components/InsightsPanel";
import { Sidebar, NAV_ITEMS } from "./components/Sidebar";
import { FiltersBar, filtrosToRango, FILTROS_INICIALES } from "./components/FiltersBar";
import type { Filtros } from "./components/FiltersBar";

function App() {
  const [resumen, setResumen] = useState<ResumenGeneral | null>(null);
  const [mensual, setMensual] = useState<ResumenMensualItem[]>([]);
  const [comercios, setComercios] = useState<ComercioItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filtros, setFiltros] = useState<Filtros>(FILTROS_INICIALES);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [active, setActive] = useState(NAV_ITEMS[0].id);
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    const rango = filtrosToRango(filtros);
    const globalFiltros = { ...rango, tipo: filtros.tipo || undefined };
    Promise.all([
      api.resumenGeneral(globalFiltros),
      api.resumenMensual(24, globalFiltros),
      api.topComercios(8, globalFiltros),
    ])
      .then(([r, m, c]) => {
        setResumen(r);
        setMensual(m);
        setComercios(c);
        setError(null);
      })
      .catch(() => setError("No se pudo conectar con la API. ¿Esta corriendo en :3000?"));
  }, [filtros]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-15% 0px -70% 0px" },
    );
    Object.values(sectionRefs.current).forEach((el) => el && observer.observe(el));
    return () => observer.disconnect();
  }, []);

  function handleNavigate(id: string) {
    setActive(id);
    setSidebarOpen(false);
    sectionRefs.current[id]?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4 text-center" style={{ color: "var(--bad)" }}>
        {error}
      </div>
    );
  }

  return (
    <div className="flex min-h-screen" style={{ background: "var(--page)" }}>
      <Sidebar
        active={active}
        ultimaActualizacion={resumen?.rango.hasta ? resumen.rango.hasta.slice(0, 10) : null}
        open={sidebarOpen}
        onNavigate={handleNavigate}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <FiltersBar filtros={filtros} onChange={setFiltros} onMenuClick={() => setSidebarOpen(true)} />

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <section
            id="resumen"
            ref={(el) => {
              sectionRefs.current.resumen = el;
            }}
            className="scroll-mt-20"
          >
            <div className="mb-5">
              <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
                Resumen general
              </h1>
              <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
                {resumen?.rango.desde && resumen?.rango.hasta
                  ? `Datos del ${resumen.rango.desde.slice(0, 10)} al ${resumen.rango.hasta.slice(0, 10)}`
                  : "Cargando..."}
              </p>
            </div>

            <div className="mb-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile label="Total gastado" value={resumen ? formatMonto(resumen.totalGastado) : "—"} />
              <StatTile label="Movimientos" value={resumen ? String(resumen.cantidadMovimientos) : "—"} />
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
            </div>

            <InsightsPanel resumen={resumen} mensual={mensual} comercios={comercios} />
          </section>

          <section
            id="tendencia"
            ref={(el) => {
              sectionRefs.current.tendencia = el;
            }}
            className="mt-8 scroll-mt-20"
          >
            <MonthlyChart data={mensual} />
          </section>

          <section
            id="comercios"
            ref={(el) => {
              sectionRefs.current.comercios = el;
            }}
            className="mt-8 scroll-mt-20"
          >
            <TopComerciosChart data={comercios} />
          </section>

          <section
            id="movimientos"
            ref={(el) => {
              sectionRefs.current.movimientos = el;
            }}
            className="mt-8 scroll-mt-20"
          >
            <MovimientosTable tipoGlobal={filtros.tipo} />
          </section>
        </main>
      </div>
    </div>
  );
}

export default App;
