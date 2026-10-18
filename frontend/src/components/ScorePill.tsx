import { isNil } from "../utils/format";
import "./components.css";

export type ScoreTier = "strong" | "moderate" | "low";

export function scoreTier(score: number | null | undefined): ScoreTier {
  if (isNil(score)) return "low";
  const value = score as number;
  if (value >= 70) return "strong";
  if (value >= 40) return "moderate";
  return "low";
}

const TIER_TITLES: Record<ScoreTier, string> = {
  strong: "Strong signal (score ≥ 70)",
  moderate: "Moderate signal (score 40–69)",
  low: "Weak signal (score < 40)",
};

interface ScorePillProps {
  score: number | null | undefined;
}

/** Evidence-score pill: ≥70 strong/red-orange, 40–69 amber, <40 slate. */
export function ScorePill({ score }: ScorePillProps) {
  const tier = scoreTier(score);
  const label = isNil(score) ? "—" : (score as number).toFixed(1);
  return (
    <span className={`score-pill score-pill--${tier}`} title={TIER_TITLES[tier]}>
      {label}
    </span>
  );
}
