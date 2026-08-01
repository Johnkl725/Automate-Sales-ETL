import type { ReactElement } from "react";

interface NavItem {
  id: string;
  label: string;
  icon: ReactElement;
}

const ICONS = {
  resumen: (
    <path d="M4 13h4v7H4v-7Zm6-6h4v13h-4V7Zm6-4h4v17h-4V3Z" />
  ),
  tendencia: (
    <path d="M3 17 9 11l4 4 8-8M15 7h6v6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
  ),
  comercios: (
    <path
      d="M4 8h16l-1 11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 8Zm2-3h12l1.5 3h-15L6 5Z"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  ),
  movimientos: (
    <path
      d="M4 6h16M4 12h16M4 18h10"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  ),
};

export const NAV_ITEMS: NavItem[] = [
  { id: "resumen", label: "Resumen", icon: ICONS.resumen },
  { id: "tendencia", label: "Tendencia mensual", icon: ICONS.tendencia },
  { id: "comercios", label: "Top comercios", icon: ICONS.comercios },
  { id: "movimientos", label: "Movimientos", icon: ICONS.movimientos },
];

interface SidebarProps {
  active: string;
  ultimaActualizacion: string | null;
  open: boolean;
  onNavigate: (id: string) => void;
  onClose: () => void;
}

export function Sidebar({ active, ultimaActualizacion, open, onNavigate, onClose }: SidebarProps) {
  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 lg:hidden"
          style={{ background: "rgba(0,0,0,0.5)" }}
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        style={{ background: "var(--surface)", borderRight: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2.5 px-5 py-5" style={{ borderBottom: "1px solid var(--border)" }}>
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-bold"
            style={{ background: "var(--series-consumo)", color: "#ffffff" }}
          >
            S/
          </span>
          <div>
            <p className="text-sm font-semibold leading-tight" style={{ color: "var(--text-primary)" }}>
              Gastos BCP
            </p>
            <p className="text-xs leading-tight" style={{ color: "var(--text-muted)" }}>
              Panel personal
            </p>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 px-3 py-4">
          {NAV_ITEMS.map((item) => {
            const isActive = active === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors"
                style={{
                  background: isActive ? "var(--page)" : "transparent",
                  color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                }}
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-4 w-4 shrink-0"
                  stroke="currentColor"
                  fill="currentColor"
                  strokeWidth="1.8"
                  style={{ color: isActive ? "var(--series-consumo)" : "var(--text-muted)" }}
                >
                  {item.icon}
                </svg>
                {item.label}
                {isActive && (
                  <span
                    className="ml-auto h-1.5 w-1.5 rounded-full"
                    style={{ background: "var(--series-consumo)" }}
                  />
                )}
              </button>
            );
          })}
        </nav>

        <div className="px-5 py-4 text-xs" style={{ borderTop: "1px solid var(--border)", color: "var(--text-muted)" }}>
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: "var(--good)" }} />
            Pipeline activo · corre 08:00 (Lima)
          </div>
          {ultimaActualizacion && <p className="mt-1">Último dato: {ultimaActualizacion}</p>}
        </div>
      </aside>
    </>
  );
}
