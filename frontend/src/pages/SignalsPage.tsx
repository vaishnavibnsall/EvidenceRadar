import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { api } from "../api/client";
import type { Signal, SignalSort } from "../api/types";
import { useAsync, useDebouncedValue } from "../hooks/useAsync";
import { PageHeader } from "../components/PageHeader";
import { DataTable, type Column } from "../components/DataTable";
import { ScorePill } from "../components/ScorePill";
import { LabelBadge } from "../components/Badge";
import { EmptyState, ErrorState, Loader } from "../components/States";
import { Pagination } from "../components/Pagination";
import { formatFloat, formatInt, formatPValue, titleCase } from "../utils/format";
import "./SignalsPage.css";

const PAGE_SIZE = 25;

const SORT_OPTIONS: Array<{ value: SignalSort; label: string }> = [
  { value: "evidence_score", label: "Evidence score" },
  { value: "cases", label: "Cases" },
  { value: "ror", label: "Reporting odds ratio" },
  { value: "eb05", label: "EB05 (Bayesian)" },
  { value: "p_value", label: "Chi² p-value" },
];

function TrendIndicator({ slope }: { slope: number | null }) {
  if (slope === null || Number.isNaN(slope)) {
    return (
      <span className="trend-flat" title="Trend not computable">
        <Minus size={15} aria-hidden />
      </span>
    );
  }
  if (slope > 0.05) {
    return (
      <span className="trend-up mono" title={`Rising trend (slope ${slope.toFixed(3)})`}>
        <ArrowUpRight size={15} aria-hidden />
      </span>
    );
  }
  if (slope < -0.05) {
    return (
      <span className="trend-down mono" title={`Falling trend (slope ${slope.toFixed(3)})`}>
        <ArrowDownRight size={15} aria-hidden />
      </span>
    );
  }
  return (
    <span className="trend-flat" title={`Flat trend (slope ${slope.toFixed(3)})`}>
      <Minus size={15} aria-hidden />
    </span>
  );
}

export function SignalsPage() {
  const navigate = useNavigate();

  const [search, setSearch] = useState("");
  const [minCases, setMinCases] = useState(3);
  const [minScore, setMinScore] = useState(0);
  const [sort, setSort] = useState<SignalSort>("evidence_score");
  const [offset, setOffset] = useState(0);

  const debouncedSearch = useDebouncedValue(search, 300);

  // Reset to the first page whenever the query changes.
  useEffect(() => {
    setOffset(0);
  }, [debouncedSearch, minCases, minScore, sort]);

  const { data, loading, error, reload } = useAsync(
    () =>
      api.signals({
        q: debouncedSearch.trim() || undefined,
        min_cases: minCases,
        min_score: minScore,
        sort,
        limit: PAGE_SIZE,
        offset,
      }),
    [debouncedSearch, minCases, minScore, sort, offset],
  );

  const columns: Column<Signal>[] = useMemo(
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
        key: "prr",
        header: "PRR",
        align: "right",
        render: (s) => (
          <span className="mono">
            {formatFloat(s.prr, 2)}
            <span className="cell-ci">{formatCI(s.prr_lo, s.prr_hi)}</span>
          </span>
        ),
      },
      {
        key: "ror",
        header: "ROR",
        align: "right",
        render: (s) => (
          <span className="mono">
            {formatFloat(s.ror, 2)}
            <span className="cell-ci">{formatCI(s.ror_lo, s.ror_hi)}</span>
          </span>
        ),
      },
      {
        key: "eb05",
        header: "EB05",
        align: "right",
        render: (s) => <span className="mono">{formatFloat(s.eb05, 2)}</span>,
      },
      {
        key: "p_value",
        header: "Chi² p",
        align: "right",
        render: (s) => <span className="mono">{formatPValue(s.p_value)}</span>,
      },
      {
        key: "trend",
        header: "Trend",
        align: "center",
        render: (s) => <TrendIndicator slope={s.trend_slope} />,
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

  const total = data?.total ?? 0;
  const pageRows = data?.signals ?? [];

  return (
    <div className="page">
      <PageHeader
        title="Disproportionality Signals"
        subtitle="FAERS drug–reaction pairs with PRR / ROR / Bayesian metrics and composite evidence scores."
      />

      <section className="panel">
        <div className="panel__body">
          <div className="signals__filters">
            <label className="field">
              <span className="field__label">Search drug or reaction</span>
              <input
                type="search"
                className="input input--search"
                placeholder="e.g. metformin, nausea…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field__label">Min. cases</span>
              <input
                type="number"
                className="input"
                min={1}
                value={minCases}
                onChange={(event) => setMinCases(clampNumber(event.target.value, 1, 500000, 3))}
              />
            </label>
            <label className="field">
              <span className="field__label">Min. score</span>
              <input
                type="number"
                className="input"
                min={0}
                max={100}
                value={minScore}
                onChange={(event) => setMinScore(clampNumber(event.target.value, 0, 100, 0))}
              />
            </label>
            <label className="field">
              <span className="field__label">Sort by</span>
              <select
                className="select"
                value={sort}
                onChange={(event) => setSort(event.target.value as SignalSort)}
              >
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div className="signals__count">
            <strong>{formatInt(total)}</strong> signal{total === 1 ? "" : "s"} match the current filters
          </div>
        </div>

        {loading && data === null ? (
          <Loader label="Loading signals…" />
        ) : error ? (
          <ErrorState title="Could not load signals" message={error.message} onRetry={reload} />
        ) : pageRows.length === 0 ? (
          <EmptyState
            title="No signals match your filters"
            message="Try lowering the minimum case count or score, or clearing the search."
            action={
              <button
                type="button"
                className="btn"
                onClick={() => {
                  setSearch("");
                  setMinCases(3);
                  setMinScore(0);
                  setSort("evidence_score");
                }}
              >
                Reset filters
              </button>
            }
          />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={pageRows}
              rowKey={(s) => `${s.drug}::${s.reaction}`}
              onRowClick={(s) => navigate(`/drug/${encodeURIComponent(s.drug)}`)}
            />
            <Pagination offset={offset} limit={PAGE_SIZE} total={total} onChange={setOffset} />
          </>
        )}
      </section>
    </div>
  );
}

function formatCI(lo: number | null, hi: number | null): string {
  if (lo === null || hi === null) return "";
  return `${lo.toFixed(2)}–${hi.toFixed(2)}`;
}

function clampNumber(raw: string, min: number, max: number, fallback: number): number {
  const parsed = Number(raw);
  if (Number.isNaN(parsed)) return fallback;
  return Math.min(max, Math.max(min, Math.round(parsed)));
}
