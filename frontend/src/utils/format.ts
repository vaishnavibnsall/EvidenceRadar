/** Number / string formatting helpers shared across the app. */

export type Tone = "cyan" | "teal" | "green" | "amber" | "red" | "slate" | "violet";

export const TONE_COLORS: Record<Tone, string> = {
  cyan: "#22d3ee",
  teal: "#2dd4bf",
  green: "#4ade80",
  amber: "#f59e0b",
  red: "#f87171",
  slate: "#94a3b8",
  violet: "#a78bfa",
};

const EM_DASH = "—";

export function isNil(value: number | null | undefined): boolean {
  return value === null || value === undefined || Number.isNaN(value);
}

/** Integer with thousands separators, e.g. 45210 → "45,210". */
export function formatInt(value: number | null | undefined, fallback = EM_DASH): string {
  if (isNil(value)) return fallback;
  return (value as number).toLocaleString("en-US");
}

/** Fixed-precision float, e.g. 71.245 → "71.2". */
export function formatFloat(value: number | null | undefined, digits = 2, fallback = EM_DASH): string {
  if (isNil(value)) return fallback;
  return (value as number).toFixed(digits);
}

/** Ratio measure with confidence interval: 3.1 (2.5–3.8). */
export function formatWithCI(value: number | null, lo: number | null, hi: number | null, digits = 2): string {
  if (isNil(value)) return EM_DASH;
  const main = (value as number).toFixed(digits);
  if (isNil(lo) || isNil(hi)) return main;
  return `${main} (${(lo as number).toFixed(digits)}–${(hi as number).toFixed(digits)})`;
}

/** Chi2 p-value — tiny values collapse to "<1e-10". */
export function formatPValue(p: number | null | undefined): string {
  if (isNil(p)) return EM_DASH;
  const value = p as number;
  if (value < 1e-10) return "<1e-10";
  if (value >= 0.001) return value.toFixed(3);
  return value.toExponential(1);
}

/** Share in [0,1] rendered as a percentage. */
export function formatShare(share: number | null | undefined, fallback = EM_DASH): string {
  if (isNil(share)) return fallback;
  return `${((share as number) * 100).toFixed(0)}%`;
}

/** Rating like 6.8 → "6.8 / 10". */
export function formatRating(rating: number | null | undefined): string {
  if (isNil(rating)) return EM_DASH;
  return `${(rating as number).toFixed(1)} / 10`;
}

/** "METFORMIN HYDROCHLORIDE" → "Metformin Hydrochloride". */
export function titleCase(name: string | null | undefined): string {
  if (!name) return EM_DASH;
  return name
    .toLowerCase()
    .replace(/(^|[\s/\-])([a-z])/g, (_match, sep: string, ch: string) => sep + ch.toUpperCase());
}

/** Sentence-case status labels: "ACTIVE_NOT_RECRUITING" → "Active, not recruiting". */
export function statusLabel(status: string | null | undefined): string {
  if (!status) return EM_DASH;
  const special: Record<string, string> = {
    ACTIVE_NOT_RECRUITING: "Active, not recruiting",
    NOT_YET_RECRUITING: "Not yet recruiting",
    ENROLLING_BY_INVITATION: "Enrolling by invitation",
    EXPANDED_ACCESS: "Expanded access",
  };
  const upper = status.toUpperCase();
  if (special[upper]) return special[upper];
  return titleCase(upper);
}

/** Tone for a trial status (drives Badge + map marker colors). */
export function statusTone(status: string | null | undefined): Tone {
  const upper = (status ?? "").toUpperCase();
  if (upper === "RECRUITING" || upper === "ENROLLING_BY_INVITATION") return "teal";
  if (upper === "ACTIVE_NOT_RECRUITING") return "cyan";
  if (upper === "COMPLETED") return "green";
  if (upper === "NOT_YET_RECRUITING" || upper === "SUSPENDED") return "amber";
  if (upper === "TERMINATED" || upper === "WITHDRAWN" || upper === "UNKNOWN") return "red";
  return "slate";
}

/** "PHASE1|PHASE2" → "Phase 1/2"; "NA" → "N/A". */
export function phaseLabel(phase: string | null | undefined): string {
  if (!phase) return EM_DASH;
  const upper = phase.toUpperCase();
  if (upper === "NA" || upper === "NOT_APPLICABLE" || upper === "") return "N/A";
  if (upper === "EARLY_PHASE1") return "Early Phase 1";
  const parts = upper.split("|").map((part) => {
    if (part.startsWith("PHASE")) {
      const num = part.slice("PHASE".length);
      return num === "0" ? "0" : num;
    }
    return titleCase(part);
  });
  return `Phase ${parts.join("/")}`;
}

export function phaseTone(phase: string | null | undefined): Tone {
  const upper = (phase ?? "").toUpperCase();
  if (upper.includes("PHASE4")) return "violet";
  if (upper.includes("PHASE3")) return "cyan";
  if (upper.includes("PHASE2")) return "teal";
  if (upper.includes("PHASE1") || upper.includes("EARLY_PHASE1")) return "amber";
  return "slate";
}

/** Color ramp for evidence scores: <40 slate/cyan, 40–69 amber, ≥70 red. */
export function scoreColor(score: number | null | undefined): string {
  if (isNil(score)) return TONE_COLORS.slate;
  const value = score as number;
  if (value >= 70) return TONE_COLORS.red;
  if (value >= 40) return TONE_COLORS.amber;
  if (value >= 20) return TONE_COLORS.teal;
  return TONE_COLORS.cyan;
}

/** Shorten long drug names for chart axes. */
export function shortLabel(name: string, max = 18): string {
  return name.length > max ? `${name.slice(0, max - 1)}…` : name;
}

/** Truncate long regulatory text for panel excerpts. */
export function truncate(text: string | null | undefined, max = 600): string {
  if (!text) return "";
  const clean = text.trim();
  return clean.length > max ? `${clean.slice(0, max).trimEnd()}…` : clean;
}

/** Format an ISO date (YYYY-MM-DD) for display; tolerant of partial dates. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return EM_DASH;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

/** "2025-04" → "Apr 2025". */
export function formatMonth(month: string | null | undefined): string {
  if (!month) return EM_DASH;
  const parsed = new Date(`${month}-01T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return month;
  return parsed.toLocaleDateString("en-US", { year: "numeric", month: "short" });
}

/** Percent used for axis ticks / progress bars. */
export function pct(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

/** Decoded, safe route param (handles malformed percent-encoding). */
export function safeDecode(value: string | undefined): string {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** Join a country list for compact table cells. */
export function joinCountries(countries: string[] | null | undefined, max = 2): string {
  if (!countries || countries.length === 0) return EM_DASH;
  if (countries.length <= max) return countries.join(", ");
  return `${countries.slice(0, max).join(", ")} +${countries.length - max}`;
}
