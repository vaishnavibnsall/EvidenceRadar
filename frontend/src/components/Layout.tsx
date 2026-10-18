import { NavLink, Outlet } from "react-router-dom";
import { Activity, Radar, FlaskConical, MessageSquareText, BookOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import "./Layout.css";

interface NavItem {
  to: string;
  label: string;
  icon: typeof Radar;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Overview", icon: Activity },
  { to: "/signals", label: "Signals", icon: Radar },
  { to: "/trials", label: "Trials", icon: FlaskConical },
  { to: "/reviews", label: "Reviews", icon: MessageSquareText },
  { to: "/methodology", label: "Methodology", icon: BookOpen },
];

/** Lightweight API liveness indicator in the sidebar footer. */
function useApiHealth(): "ok" | "down" | "unknown" {
  const [health, setHealth] = useState<"ok" | "down" | "unknown">("unknown");

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then(() => {
        if (!cancelled) setHealth("ok");
      })
      .catch(() => {
        if (!cancelled) setHealth("down");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return health;
}

export function Layout() {
  const health = useApiHealth();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to="/" className="sidebar__brand" end>
          <span className="sidebar__mark" aria-hidden>
            ◉
          </span>
          <span className="sidebar__brand-text">
            EvidenceRadar
            <span className="sidebar__brand-sub">RWE Pharmacovigilance</span>
          </span>
        </NavLink>

        <nav className="sidebar__nav" aria-label="Primary">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              title={label}
              className={({ isActive }) => `sidebar__link${isActive ? " active" : ""}`}
            >
              <Icon size={18} aria-hidden />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__footer">
          <div
            className="sidebar__health"
            title={
              health === "ok"
                ? "Backend connected"
                : health === "down"
                  ? "Backend unreachable"
                  : "Checking backend…"
            }
          >
            <span
              className={`sidebar__dot${
                health === "ok" ? " sidebar__dot--ok" : health === "down" ? " sidebar__dot--err" : ""
              }`}
            />
            <span className="sidebar__footer-text">
              {health === "ok" ? "API connected" : health === "down" ? "API offline" : "Checking API…"}
            </span>
          </div>
          <span className="sidebar__footer-text">FAERS · CT.gov · Reviews</span>
        </div>
      </aside>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
