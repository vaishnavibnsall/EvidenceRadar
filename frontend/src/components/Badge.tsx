import type { ReactNode } from "react";
import { phaseLabel, phaseTone, statusLabel, statusTone, type Tone } from "../utils/format";
import "./components.css";

export type BadgeTone = Tone;

interface BadgeProps {
  tone?: BadgeTone;
  children: ReactNode;
  title?: string;
}

export function Badge({ tone = "slate", children, title }: BadgeProps) {
  return (
    <span className={`badge badge--${tone}`} title={title}>
      {children}
    </span>
  );
}

/** Labelled (on-label) vs. off-label indication badge. */
export function LabelBadge({ inLabel }: { inLabel: boolean }) {
  return inLabel ? (
    <Badge tone="teal" title="Reaction is listed in the FDA label">
      Labelled
    </Badge>
  ) : (
    <Badge tone="slate" title="Reaction is not listed in the FDA label">
      Unlabelled
    </Badge>
  );
}

/** Trial overall-status badge with domain colors. */
export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={statusTone(status)}>{statusLabel(status)}</Badge>;
}

/** Trial phase badge ("PHASE1|PHASE2" → "Phase 1/2"). */
export function PhaseBadge({ phase }: { phase: string }) {
  return <Badge tone={phaseTone(phase)}>{phaseLabel(phase)}</Badge>;
}
