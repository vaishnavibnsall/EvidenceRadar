import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import {
  Activity,
  FlaskConical,
  MessageSquareText,
  Radar,
  Tag,
  TrendingUp,
} from "lucide-react";
import { api } from "../api/client";
import type { Signal } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { ScorePill } from "../components/ScorePill";
import { Badge, LabelBadge } from "../components/Badge";
import { DataTable, type Column } from "../components/DataTable";
import { EmptyState, ErrorState, Loader } from "../components/States";
import {
  formatFloat,
  formatInt,
  formatMonth,
  scoreColor,
  shortLabel,
  titleCase,
} from "../utils/format";
import "./OverviewPage.css";

/* ------------------------------------------------------------ chart tips */

interface TrendTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: { month: string; cases: number } }>;
  label?: string;
}

function TrendTooltip({ active, payload }: TrendTooltipProps) {
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

interface TopDrugTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: { drug: string; cases: number } }>;
}

function TopDrugTooltip({ active, payload }: TopDrugTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const { drug, cases } = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title">{titleCase(drug)}</div>
      <div className="chart-tooltip__row">
        <span>Cases</span>
        <strong>{formatInt(cases)}</strong>
      </div>
    </div>
  );
}

interface ScatterPoint {
  key: string;
  drug: string;
  reaction: string;
  x: number; // log10(cases)
  y: number; // ror, capped
  z: number; // evidence_score
  cases: number;
  ror: number | null;
  score: number | null;
}

function ScatterTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ScatterPoint }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title">
        {titleCase(point.drug)} → {titleCase(point.reaction)}
      </div>
      <div className="chart-tooltip__row">
        <span>Cases</span>
        <strong>{formatInt(point.cases)}</strong>
      </div>
      <div className="chart-tooltip__row">
        <span>ROR</span>
        <strong>{point.ror === null ? "—" : `${point.ror.toFixed(2)}${point.ror >= 20 ? " (capped)" : ""}`}</strong>
      </div>
      <div className="chart-tooltip__row">
        <span>Evidence score</span>
        <strong>{point.score === null ? "—" : point.score.toFixed(1)}</strong>
      </div>
    </div>
  );
}

const ROR_DISPLAY_CAP = 20;

/* ------------------------------------------------------------------ page */

export function OverviewPage() {
  const navigate = useNavigate();

  const overview = useAsync(() => api.overview(), []);
  const topSignals = useAsync(
    () => api.signals({ limit: 10, sort: "evidence_score", min_cases: 3 }),
    [],
  );
  const scatterSignals = useAsync(() => api.signals({ limit: 200 }), []);

  const scatterPoints = useMemo<ScatterPoint[]>(() => {
    const signals = scatterSignals.data?.signals ?? [];
    return signals
      .filter((s) => s.cases > 0)
      .map((s, index) => ({
        key: `${s.drug}-${s.reaction}-${index}`,
        drug: s.drug,
        reaction: s.reaction,
        x: Math.log10(s.cases),
        y: s.ror === null ? 0 : Math.min(s.ror, ROR_DISPLAY_CAP),
        z: s.evidence_score === null ? 1 : s.evidence_score,
        cases: s.cases,
        ror: s.ror,
        score: s.evidence_score,
      }));
  }, [scatterSignals.data]);

  const signalColumns: Column<Signal>[] = useMemo(
    () => [
      {
        key: "drug",
        header: "Drug",
        render: (s) => <span className="cell-strong">{titleCase(s.drug)}</span>,
      },
      {
        key: "reaction",
        header: "Reaction",
        render: (s) => titleCase(s.reaction),
      },
      {
        key: "cases",
        header: "Cases",
        align: "right",
        render: (s) => <span className="mono">{formatInt(s.cases)}</span>,
      },
      {
        key: "ror",
        header: "ROR",
        align: "right",
        render: (s) => <span className="mono">{formatFloat(s.ror, 2)}</span>,
      },
      {
        key: "eb05",
        header: "EB05",
        align: "right",
        render: (s) => <span className="mono">{formatFloat(s.eb05, 2)}</span>,
      },
      {
        key: "score",
        header: "Score",
        align: "center",
        render: (s) => <ScorePill score={s.evidence_score} />,
      },
      {
        key: "in_label",
        header: "Label",
        align: "center",
        render: (s) => <LabelBadge inLabel={s.in_label} />,
      },
    ],
    [],
  );

  const range = overview.data?.date_range;
  const rangeLabel = range ? `${formatMonth(range.from)} – ${formatMonth(range.to)}` : "";

  return (
    <div className="page">
      <PageHeader
        title="Overview"
        subtitle={
          <>
            Real-world evidence at a glance{" "}
            {rangeLabel ? <span className="faint">· FAERS {rangeLabel}</span> : null}
          </>
        }
        actions={
          overview.data ? (
            <div className="overview__meta">
              <Badge tone="cyan">{`Source: ${overview.data.source}`}</Badge>
              <span className="overview__section-note">
                Refreshed {new Date(overview.data.last_refresh).toLocaleString()}
              </span>
            </div>
          ) : null
        }
      />

      {overview.error ? (
        <div className="panel">
          <ErrorState
            title="Could not load the overview"
            message={overview.error.message}
            onRetry={overview.reload}
          />
        </div>
      ) : null}

      <div className="kpi-grid">
        <StatCard
          label="FAERS Cases"
          value={overview.data?.cases}
          icon={Activity}
          loading={overview.loading}
          hint="Total reports in range"
        />
        <StatCard
          label="Unique Drugs"
          value={overview.data?.unique_drugs}
          icon={Tag}
          loading={overview.loading}
        />
        <StatCard
          label="Reactions"
          value={overview.data?.unique_reactions}
          icon={TrendingUp}
          loading={overview.loading}
          hint="Unique preferred terms"
        />
        <StatCard
          label="Trials"
          value={overview.data?.trials}
          icon={FlaskConical}
          loading={overview.loading}
          hint="ClinicalTrials.gov studies"
        />
        <StatCard
          label="Reviews"
          value={overview.data?.reviews}
          icon={MessageSquareText}
          loading={overview.loading}
          hint="Patient reviews analysed"
        />
        <StatCard
          label="Strong Signals"
          value={overview.data?.strong_signals}
          icon={Radar}
          loading={overview.loading}
          hint="Evidence score ≥ 70"
        />
      </div>

      <div className="panel-grid panel-grid--main-side">
        <section className="panel">
          <div className="panel__head">
            <div>
              <div className="panel__title">Global FAERS case volume</div>
              <div className="panel__subtitle">Monthly adverse-event reports</div>
            </div>
          </div>
          <div className="panel__body">
            {overview.loading ? (
              <Loader label="Loading trend…" />
            ) : overview.error ? (
              <ErrorState message={overview.error.message} onRetry={overview.reload} />
            ) : (overview.data?.global_trend.length ?? 0) === 0 ? (
              <EmptyState title="No trend data" message="The backend returned no monthly cases." />
            ) : (
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={overview.data?.global_trend} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                    <defs>
                      <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.42} />
                        <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.02} />
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
                    <Tooltip content={<TrendTooltip />} cursor={{ stroke: "#334155" }} />
                    <Area
                      type="monotone"
                      dataKey="cases"
                      name="Cases"
                      stroke="#22d3ee"
                      strokeWidth={2}
                      fill="url(#trendFill)"
                      dot={false}
                      activeDot={{ r: 4, fill: "#22d3ee", stroke: "#0a0f1e", strokeWidth: 2 }}
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
              <div className="panel__title">Top drugs by cases</div>
              <div className="panel__subtitle">Most reported actives in FAERS</div>
            </div>
          </div>
          <div className="panel__body">
            {overview.loading ? (
              <Loader label="Loading top drugs…" />
            ) : overview.error ? (
              <ErrorState message={overview.error.message} onRetry={overview.reload} />
            ) : (overview.data?.top_drugs.length ?? 0) === 0 ? (
              <EmptyState title="No drug data" message="The backend returned no top drugs." />
            ) : (
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={overview.data?.top_drugs}
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
                      dataKey="drug"
                      width={128}
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(value: string) => shortLabel(value, 18)}
                    />
                    <Tooltip content={<TopDrugTooltip />} cursor={{ fill: "rgba(34,211,238,0.06)" }} />
                    <Bar dataKey="cases" name="Cases" radius={[0, 4, 4, 0]} barSize={14}>
                      {(overview.data?.top_drugs ?? []).map((drug, index, all) => (
                        <Cell
                          key={drug.drug}
                          fill="#22d3ee"
                          fillOpacity={Math.max(0.35, 1 - index * (0.6 / Math.max(1, all.length)))}
                        />
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
            <div className="panel__title">Top signals</div>
            <div className="panel__subtitle">Highest evidence scores · min. 3 cases</div>
          </div>
          <button type="button" className="btn" onClick={() => navigate("/signals")}>
            View all signals
          </button>
        </div>
        <div className="panel__body panel__body--flush">
          {topSignals.loading ? (
            <Loader label="Loading signals…" />
          ) : topSignals.error ? (
            <ErrorState message={topSignals.error.message} onRetry={topSignals.reload} />
          ) : (topSignals.data?.signals.length ?? 0) === 0 ? (
            <EmptyState
              title="No signals found"
              message="Try lowering the minimum case threshold on the Signals page."
            />
          ) : (
            <DataTable
              columns={signalColumns}
              rows={(topSignals.data?.signals ?? []).slice(0, 10)}
              rowKey={(s) => `${s.drug}::${s.reaction}`}
              onRowClick={(s) => navigate(`/drug/${encodeURIComponent(s.drug)}`)}
            />
          )}
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <div className="panel__title">Signal landscape</div>
            <div className="panel__subtitle">
              log₁₀(cases) vs. reporting odds ratio · bubble size = evidence score (first 200 signals)
            </div>
          </div>
        </div>
        <div className="panel__body">
          {scatterSignals.loading ? (
            <Loader label="Loading signal landscape…" />
          ) : scatterSignals.error ? (
            <ErrorState message={scatterSignals.error.message} onRetry={scatterSignals.reload} />
          ) : scatterPoints.length === 0 ? (
            <EmptyState
              title="No signals to plot"
              message="The backend returned no signals for the scatter plot."
            />
          ) : (
            <>
              <div className="chart-box--scatter">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 10, right: 20, left: 4, bottom: 12 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis
                      type="number"
                      dataKey="x"
                      name="log10(cases)"
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickLine={false}
                      axisLine={{ stroke: "#1e293b" }}
                      label={{
                        value: "log₁₀(cases)",
                        position: "insideBottom",
                        offset: -8,
                        fill: "#64748b",
                        fontSize: 11,
                      }}
                    />
                    <YAxis
                      type="number"
                      dataKey="y"
                      name="ROR"
                      domain={[0, ROR_DISPLAY_CAP]}
                      tick={{ fill: "#94a3b8", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      width={44}
                      label={{
                        value: `ROR (capped at ${ROR_DISPLAY_CAP})`,
                        angle: -90,
                        position: "insideLeft",
                        offset: 8,
                        fill: "#64748b",
                        fontSize: 11,
                      }}
                    />
                    <ZAxis type="number" dataKey="z" range={[30, 420]} name="Evidence score" />
                    <Tooltip
                      content={<ScatterTooltip />}
                      cursor={{ strokeDasharray: "3 3", stroke: "#334155" }}
                    />
                    <Scatter data={scatterPoints} fillOpacity={0.5}>
                      {scatterPoints.map((point) => (
                        <Cell key={point.key} fill={scoreColor(point.score)} />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
              <p className="overview__section-note overview__section-note--spaced">
                Colors: cyan/teal = low score, amber = moderate (40–69), red = strong (≥ 70). ROR
                values above {ROR_DISPLAY_CAP} are flattened for readability.
              </p>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
