import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { formatInt } from "../utils/format";
import "./components.css";

interface StatCardProps {
  label: string;
  value: number | string | null | undefined;
  hint?: string;
  icon?: LucideIcon;
  loading?: boolean;
  /** Optional custom renderer (e.g. a ScorePill instead of a raw number). */
  render?: () => ReactNode;
}

export function StatCard({ label, value, hint, icon: Icon, loading, render }: StatCardProps) {
  return (
    <div className="stat-card">
      <div className="stat-card__top">
        <span className="stat-card__label">{label}</span>
        {Icon ? <Icon size={17} className="stat-card__icon" aria-hidden /> : null}
      </div>
      {loading ? (
        <div className="stat-card__skeleton" aria-hidden />
      ) : (
        <div className="stat-card__value">
          {render
            ? render()
            : typeof value === "number"
              ? formatInt(value)
              : (value ?? "—")}
        </div>
      )}
      <div className="stat-card__hint">{hint ?? ""}</div>
    </div>
  );
}
