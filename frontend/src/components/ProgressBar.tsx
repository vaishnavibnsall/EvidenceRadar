import { formatShare } from "../utils/format";
import "./components.css";

interface ProgressBarProps {
  label: string;
  /** Share in [0, 1]. */
  value: number | null;
  tone?: "accent" | "amber" | "red" | "green";
}

const TONE_CLASS: Record<NonNullable<ProgressBarProps["tone"]>, string> = {
  accent: "",
  amber: " progress__fill--amber",
  red: " progress__fill--red",
  green: " progress__fill--green",
};

export function ProgressBar({ label, value, tone = "accent" }: ProgressBarProps) {
  const pctValue = value === null || Number.isNaN(value) ? 0 : Math.min(1, Math.max(0, value));
  return (
    <div className="progress">
      <div className="progress__row">
        <span>{label}</span>
        <span className="progress__value">{formatShare(value)}</span>
      </div>
      <div
        className="progress__track"
        role="progressbar"
        aria-valuenow={Math.round(pctValue * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div className={`progress__fill${TONE_CLASS[tone]}`} style={{ width: `${pctValue * 100}%` }} />
      </div>
    </div>
  );
}

/** Small count chip, e.g. an ADR term: "nausea · 44". */
export function TermChip({
  term,
  count,
  variant = "accent",
}: {
  term: string;
  count?: number;
  variant?: "accent" | "plain";
}) {
  return (
    <span className={`chip${variant === "plain" ? " chip--plain" : ""}`}>
      {term}
      {count !== undefined ? <span className="chip__count">{count.toLocaleString()}</span> : null}
    </span>
  );
}
