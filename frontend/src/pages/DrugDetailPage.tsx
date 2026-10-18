import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowLeft,
  Boxes,
  ExternalLink,
  FlaskConical,
  MessageSquareText,
  Radar,
  SearchX,
  Tag,
  TriangleAlert,
} from "lucide-react";
import { api } from "../api/client";
import type { DrugPair, DrugReaction } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { ScorePill } from "../components/ScorePill";
import { LabelBadge, PhaseBadge, StatusBadge } from "../components/Badge";
import { DataTable, type Column } from "../components/DataTable";
import { EmptyState, ErrorState, Loader } from "../components/States";
import { ProgressBar, TermChip } from "../components/ProgressBar";
import {
  formatFloat,
  formatInt,
  formatMonth,
  formatRating,
  safeDecode,
  scoreColor,
  shortLabel,
  titleCase,
  truncate,
} from "../utils/format";
import "./DrugDetailPage.css";

/* ------------------------------------------------------------ chart tips */

function DrugTrendTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: { month: string; cases: number } }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const { month, cases } = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title">{formatMonth(month)}</div>
      <div className="chart-tooltip__row">
        <span>Cases</span>
        <strong>{formatInt(cases)}</strong>
      </div>
    </div>
  );
}

function ReactionBarTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: { reaction: string; cases: number; score: number | null } }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const { reaction, cases, score } = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title">{titleCase(reaction)}</div>
      <div className="chart-tooltip__row">
        <span>Cases</span>
        <strong>{formatInt(cases)}</strong>
      </div>
      <div className="chart-tooltip__row">
        <span>Evidence score</span>
        <strong>{score === null ? "—" : score.toFixed(1)}</strong>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ page */

export function DrugDetailPage() {
  const params = useParams<{ name: string }>();
  const drugName = safeDecode(params.name);

  const { data, loading, error, reload } = useAsync(() => api.drug(drugName), [drugName]);

  const reactionColumns: Column<DrugReaction>[] = useMemo(
    () => [
      {
        key: "reaction",
        header: "Reaction",
        render: (r) => (
          <span className="cell-strong">
            {titleCase(r.reaction)} {r.in_label ? <LabelBadge inLabel /> : null}
          </span>
        ),
      },
      {
        key: "cases",
        header: "Cases",
        align: "right",
        sortValue: (r) => r.cases,
        render: (r) => <span className="mono">{formatInt(r.cases)}</span>,
      },
      {
        key: "prr",
        header: "PRR",
        align: "right",
        sortValue: (r) => r.prr,
        render: (r) => <span className="mono">{formatFloat(r.prr, 2)}</span>,
      },
      {
        key: "ror",
        header: "ROR",
        align: "right",
        sortValue: (r) => r.ror,
        render: (r) => <span className="mono">{formatFloat(r.ror, 2)}</span>,
      },
      {
        key: "eb05",
        header: "EB05",
        align: "right",
        sortValue: (r) => r.eb05,
        render: (r) => <span className="mono">{formatFloat(r.eb05, 2)}</span>,
      },
      {
        key: "score",
        header: "Score",
        align: "center",
        sortValue: (r) => r.evidence_score,
        render: (r) => <ScorePill score={r.evidence_score} />,
      },
    ],
    [],
  );

  const pairColumns: Column<DrugPair>[] = useMemo(
    () => [
      {
        key: "drug",
        header: "Co-reported drug",
        render: (p) => (
          <Link
            to={`/drug/${encodeURIComponent(p.drug)}`}
            onClick={(event) => event.stopPropagation()}
          >
            {titleCase(p.drug)}
          </Link>
        ),
      },
      {
        key: "co_reports",
        header: "Co-reports",
        align: "right",
        sortValue: (p) => p.co_reports,
        render: (p) => <span className="mono">{formatInt(p.co_reports)}</span>,
      },
      {
        key: "lift",
        header: "Lift",
        align: "right",
        sortValue: (p) => p.lift,
        render: (p) =>
          p.lift === null ? (
            <span className="mono">—</span>
          ) : (
            <span className={`mono${p.lift > 2 ? " lift-high" : ""}`} title={p.lift > 2 ? "Co-occurrence > 2× expected" : undefined}>
              {p.lift.toFixed(2)}×
            </span>
          ),
      },
    ],
    [],
  );

  if (!drugName) {
    return (
      <div className="page">
        <EmptyState
          title="No drug specified"
          message="Open a drug from the Signals or Reviews page."
          action={
            <Link className="btn btn--primary" to="/signals">
              <ArrowLeft size={15} aria-hidden />
              Back to Signals
            </Link>
          }
        />
      </div>
    );
  }

  if (error && "status" in error && (error as { status: number }).status === 404) {
    return (
      <div className="page">
        <PageHeader title={titleCase(drugName)} />
        <section className="panel">
          <EmptyState
            icon={<SearchX size={30} />}
            title="Drug not found"
            message={`No records for “${titleCase(drugName)}” in the EvidenceRadar database. The name may differ from the FAERS entry, or the drug has no reports.`}
            action={
              <Link className="btn btn--primary" to="/signals">
                <ArrowLeft size={15} aria-hidden />
                Back to Signals
              </Link>
            }
          />
        </section>
      </div>
    );
  }

  if (loading || (!data && !error)) {
    return (
      <div className="page">
        <PageHeader title={titleCase(drugName)} subtitle="Loading drug profile…" />
        <Loader label={`Loading ${titleCase(drugName)}…`} />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page">
        <PageHeader title={titleCase(drugName)} />
        <section className="panel">
          <ErrorState
            title="Could not load this drug"
            message={error?.message ?? "Unknown error."}
            onRetry={reload}
            action={
              <Link className="btn" to="/signals">
                <ArrowLeft size={15} aria-hidden />
                Back to Signals
              </Link>
            }
          />
        </section>
      </div>
    );
  }

  const { summary, reactions, trend, pairs, reviews, label, trials } = data;
  const topReactions = [...reactions].sort((a, b) => b.cases - a.cases).slice(0, 15);

  return (
    <div className="page">
      <PageHeader
        title={<span className="drug-header__name">{titleCase(data.drug)}</span>}
        subtitle={
          <span className="drug-header__sub">
            {summary.top_reaction
              ? `Top reaction: ${titleCase(summary.top_reaction)} · ${formatInt(summary.top_reaction_cases)} cases · `
              : ""}
            {summary.label_present ? "FDA label on file" : "No FDA label on file"}
          </span>
        }
        actions={
          <Link className="btn" to="/signals">
            <ArrowLeft size={15} aria-hidden />
            Back to Signals
          </Link>
        }
      />

      <div className="kpi-grid">
        <StatCard label="FAERS Cases" value={summary.cases} icon={Radar} />
        <StatCard label="Reactions" value={summary.reactions} icon={Tag} />
        <StatCard
          label="Max Score"
          value={null}
          icon={TriangleAlert}
          render={() => <ScorePill score={summary.max_score} />}
          hint="Strongest reaction signal"
        />
        <StatCard label="Trials" value={summary.trials} icon={FlaskConical} />
        <StatCard label="Reviews" value={summary.reviews} icon={MessageSquareText} />
        <StatCard
          label="Mean Rating"
          value={formatRating(summary.mean_rating)}
          icon={Boxes}
          hint={summary.mean_rating === null ? "No review data" : "Patient review average / 10"}
        />
      </div>

      <div className="panel-grid panel-grid--main-side">
        <section className="panel">
          <div className="panel__head">
            <div>
              <div className="panel__title">Monthly case trend</div>
              <div className="panel__subtitle">FAERS reports mentioning {titleCase(data.drug)}</div>
            </div>
          </div>
          <div className="panel__body">
            {trend.length === 0 ? (
              <EmptyState title="No trend data" message="No monthly cases were returned." />
            ) : (
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trend} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                    <defs>
                      <linearGradient id="drugTrendFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#2dd4bf" stopOpacity={0.42} />
                        <stop offset="100%" stopColor="#2dd4bf" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis
                      dataKey="month"
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickLine={false}
                      axisLine={{ stroke: "#1e293b" }}
                      minTickGap={28}
                      tickFormatter={(value: string) => formatMonth(value)}
                    />
                    <YAxis
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      width={48}
                      tickFormatter={(value: number) => formatInt(value)}
                    />
                    <Tooltip content={<DrugTrendTooltip />} cursor={{ stroke: "#334155" }} />
                    <Area
                      type="monotone"
                      dataKey="cases"
                      name="Cases"
                      stroke="#2dd4bf"
                      strokeWidth={2}
                      fill="url(#drugTrendFill)"
                      dot={false}
                      activeDot={{ r: 4, fill: "#2dd4bf", stroke: "#0a0f1e", strokeWidth: 2 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel__head">
            <div>
              <div className="panel__title">Top reactions</div>
              <div className="panel__subtitle">Top 15 by cases · color = evidence score</div>
            </div>
          </div>
          <div className="panel__body">
            {topReactions.length === 0 ? (
              <EmptyState title="No reactions" message="No reaction rows were returned." />
            ) : (
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={topReactions}
                    layout="vertical"
                    margin={{ top: 4, right: 18, left: 4, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickLine={false}
                      axisLine={{ stroke: "#1e293b" }}
                      tickFormatter={(value: number) => formatInt(value)}
                    />
                    <YAxis
                      type="category"
                      dataKey="reaction"
                      width={120}
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(value: string) => shortLabel(value, 17)}
                    />
                    <Tooltip
                      content={<ReactionBarTooltip />}
                      cursor={{ fill: "rgba(34,211,238,0.06)" }}
                    />
                    <Bar dataKey="cases" name="Cases" radius={[0, 4, 4, 0]} barSize={13}>
                      {topReactions.map((reaction) => (
                        <Cell key={reaction.reaction} fill={scoreColor(reaction.evidence_score)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="panel__head">
          <div>
            <div className="panel__title">All reactions</div>
            <div className="panel__subtitle">
              {formatInt(reactions.length)} reported preferred terms · sorted by cases
            </div>
          </div>
        </div>
        <div className="panel__body panel__body--flush">
          {reactions.length === 0 ? (
            <EmptyState title="No reactions" message="No reaction rows were returned." />
          ) : (
            <DataTable
              columns={reactionColumns}
              rows={reactions}
              rowKey={(r) => r.reaction}
              initialSort={{ key: "cases", direction: "desc" }}
            />
          )}
        </div>
      </section>

      <div className="panel-grid panel-grid--2">
        <section className="panel">
          <div className="panel__head">
            <div>
              <div className="panel__title">Co-reported drugs</div>
              <div className="panel__subtitle">Frequent co-occurrences · lift &gt; 2 highlighted</div>
            </div>
          </div>
          <div className="panel__body panel__body--flush">
            {pairs.length === 0 ? (
              <EmptyState title="No co-reported drugs" message="No drug pairs were returned." />
            ) : (
              <DataTable
                columns={pairColumns}
                rows={pairs}
                rowKey={(p) => p.drug}
                initialSort={{ key: "co_reports", direction: "desc" }}
              />
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel__head">
            <div>
              <div className="panel__title">Patient reviews</div>
              <div className="panel__subtitle">
                {reviews ? `${formatInt(reviews.reviews)} reviews aggregated` : "No review data"}
              </div>
            </div>
          </div>
          <div className="panel__body">
            {!reviews || reviews.reviews === 0 ? (
              <EmptyState
                title="No reviews yet"
                message="Patient review data is not available for this drug."
              />
            ) : (
              <>
                <div className="reviews-panel__score">
                  <span className="reviews-panel__value">
                    {formatRating(reviews.mean_rating)}
                  </span>
                  <span className="reviews-panel__max">mean rating</span>
                </div>
                <div className="reviews-panel__bars">
                  <ProgressBar
                    label="Negative sentiment share"
                    value={reviews.neg_share}
                    tone="red"
                  />
                  <ProgressBar
                    label="Positive sentiment share"
                    value={reviews.pos_share}
                    tone="green"
                  />
                  <ProgressBar
                    label="Low-rating share (≤ 4/10)"
                    value={reviews.low_rating_share}
                    tone="amber"
                  />
                </div>
                {reviews.adr_terms.length > 0 ? (
                  <>
                    <div className="reviews-panel__terms-title">Top ADR terms in reviews</div>
                    <div className="chip-row">
                      {reviews.adr_terms.slice(0, 14).map((term) => (
                        <TermChip key={term.term} term={term.term} count={term.count} />
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="muted">No ADR terms were extracted from reviews.</p>
                )}
              </>
            )}
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="panel__head">
          <div>
            <div className="panel__title">FDA label</div>
            <div className="panel__subtitle">
              {label && label.has_label
                ? `Structured product label${label.brand_name ? ` · brand: ${label.brand_name}` : ""}`
                : "No FDA label on file"}
            </div>
          </div>
        </div>
        <div className="panel__body">
          {!label || !label.has_label ? (
            <EmptyState
              title="No label available"
              message="No FDA structured product label was matched for this drug."
            />
          ) : (
            <>
              {label.boxed_warning ? (
                <div className="label-panel__warning">
                  <TriangleAlert size={17} aria-hidden />
                  Boxed warning (black box) — see full label for details
                </div>
              ) : null}

              {label.indications ? (
                <div className="label-panel__section">
                  <div className="label-panel__section-title">Indications &amp; usage</div>
                  <p className="label-panel__text">{truncate(label.indications, 600)}</p>
                </div>
              ) : null}

              {label.adverse_reactions ? (
                <div className="label-panel__section">
                  <div className="label-panel__section-title">Adverse reactions</div>
                  <p className="label-panel__text">{truncate(label.adverse_reactions, 600)}</p>
                </div>
              ) : null}

              {label.warnings ? (
                <div className="label-panel__section">
                  <div className="label-panel__section-title">Warnings</div>
                  <p className="label-panel__text">{truncate(label.warnings, 600)}</p>
                </div>
              ) : null}

              <div className="label-panel__footer">
                <span>
                  Generic: {label.generic_name ? titleCase(label.generic_name) : "—"}
                  {label.brand_name ? ` · Brand: ${label.brand_name}` : ""}
                </span>
                {label.source_url ? (
                  <a href={label.source_url} target="_blank" rel="noreferrer">
                    View source on openFDA <ExternalLink size={12} aria-hidden />
                  </a>
                ) : null}
              </div>
            </>
          )}
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <div className="panel__title">Clinical trials</div>
            <div className="panel__subtitle">
              {trials.length > 0
                ? `${formatInt(trials.length)} trials from ClinicalTrials.gov`
                : "No trials returned"}
            </div>
          </div>
        </div>
        {trials.length === 0 ? (
          <EmptyState
            title="No linked trials"
            message="No ClinicalTrials.gov studies were matched for this drug."
          />
        ) : (
          <div className="trial-list">
            {trials.map((trial) => (
              <div key={trial.nct_id} className="trial-item">
                <a
                  className="trial-item__id"
                  href={`https://clinicaltrials.gov/study/${trial.nct_id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {trial.nct_id}
                </a>
                <div>
                  <div className="trial-item__title">{trial.brief_title}</div>
                  <div className="trial-item__meta">
                    <span>Enrollment: {formatInt(trial.enrollment)}</span>
                    {trial.conditions.length > 0 ? (
                      <span>· {trial.conditions.slice(0, 3).join(", ")}</span>
                    ) : null}
                  </div>
                </div>
                <div className="trial-item__badges">
                  <PhaseBadge phase={trial.phase} />
                  <StatusBadge status={trial.overall_status} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
