import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import type { ReviewStat } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { PageHeader } from "../components/PageHeader";
import { DataTable, type Column } from "../components/DataTable";
import { EmptyState, ErrorState, Loader } from "../components/States";
import { TermChip } from "../components/ProgressBar";
import { formatFloat, formatInt, formatShare, titleCase } from "../utils/format";
import "./ReviewsPage.css";

const FETCH_LIMIT = 50;

interface RatingPoint {
  drug: string;
  reviews: number;
  mean_rating: number;
}

function RatingTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: RatingPoint }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const { drug, reviews, mean_rating } = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title">{titleCase(drug)}</div>
      <div className="chart-tooltip__row">
        <span>Mean rating</span>
        <strong>{mean_rating.toFixed(1)} / 10</strong>
      </div>
      <div className="chart-tooltip__row">
        <span>Reviews</span>
        <strong>{formatInt(reviews)}</strong>
      </div>
    </div>
  );
}

interface AdrPoint {
  term: string;
  count: number;
}

function AdrTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: AdrPoint }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const { term, count } = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__title">{titleCase(term)}</div>
      <div className="chart-tooltip__row">
        <span>Mentions</span>
        <strong>{formatInt(count)}</strong>
      </div>
    </div>
  );
}

export function ReviewsPage() {
  const navigate = useNavigate();
  const { data, loading, error, reload } = useAsync(
    () => api.reviewStats({ limit: FETCH_LIMIT, sort: "reviews" }),
    [],
  );

  const drugs = data?.drugs ?? [];

  const ratingChart = useMemo<RatingPoint[]>(
    () =>
      drugs
        .filter((d) => d.mean_rating !== null)
        .slice()
        .sort((a, b) => b.reviews - a.reviews)
        .slice(0, 20)
        .map((d) => ({
          drug: d.drug,
          reviews: d.reviews,
          mean_rating: d.mean_rating as number,
        })),
    [drugs],
  );

  const adrTerms = useMemo<AdrPoint[]>(() => {
    const totals = new Map<string, number>();
    for (const drug of drugs) {
      for (const term of drug.adr_terms ?? []) {
        const key = term.term.toLowerCase();
        totals.set(key, (totals.get(key) ?? 0) + term.count);
      }
    }
    return [...totals.entries()]
      .map(([term, count]) => ({ term, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 25);
  }, [drugs]);

  const columns: Column<ReviewStat>[] = useMemo(
    () => [
      {
        key: "drug",
        header: "Drug",
        sortValue: (d) => d.drug,
        render: (d) => (
          <Link
            className="cell-strong"
            to={`/drug/${encodeURIComponent(d.drug)}`}
            onClick={(event) => event.stopPropagation()}
          >
            {titleCase(d.drug)}
          </Link>
        ),
      },
      {
        key: "reviews",
        header: "Reviews",
        align: "right",
        sortValue: (d) => d.reviews,
        render: (d) => <span className="mono">{formatInt(d.reviews)}</span>,
      },
      {
        key: "mean_rating",
        header: "Mean rating",
        align: "right",
        sortValue: (d) => d.mean_rating,
        render: (d) => (
          <span className="mono cell-strong">{formatFloat(d.mean_rating, 1)}</span>
        ),
      },
      {
        key: "low_rating_share",
        header: "Low-rating share",
        align: "right",
        sortValue: (d) => d.low_rating_share,
        render: (d) => <span className="mono">{formatShare(d.low_rating_share)}</span>,
      },
      {
        key: "neg_share",
        header: "Negative share",
        align: "right",
        sortValue: (d) => d.neg_share,
        render: (d) => <span className="mono">{formatShare(d.neg_share)}</span>,
      },
      {
        key: "pos_share",
        header: "Positive share",
        align: "right",
        sortValue: (d) => d.pos_share,
        render: (d) => <span className="mono">{formatShare(d.pos_share)}</span>,
      },
      {
        key: "adr_terms",
        header: "Top ADR terms",
        render: (d) => (
          <span className="reviews__terms-cell">
            {(d.adr_terms ?? []).slice(0, 5).map((term) => (
              <TermChip key={term.term} term={term.term} count={term.count} />
            ))}
            {(d.adr_terms ?? []).length === 0 ? <span className="faint">—</span> : null}
          </span>
        ),
      },
    ],
    [],
  );

  return (
    <div className="page">
      <PageHeader
        title="Patient Reviews"
        subtitle="Sentiment and adverse-event mentions extracted from aggregated patient reviews."
      />

      {error ? (
        <section className="panel">
          <ErrorState title="Could not load review stats" message={error.message} onRetry={reload} />
        </section>
      ) : null}

      {loading && !data ? (
        <Loader label="Loading review stats…" />
      ) : !error && drugs.length === 0 ? (
        <section className="panel">
          <EmptyState
            title="No review data"
            message="The backend returned no patient review statistics."
          />
        </section>
      ) : null}

      {!error && drugs.length > 0 ? (
        <>
          <div className="panel-grid panel-grid--2">
            <section className="panel">
              <div className="panel__head">
                <div>
                  <div className="panel__title">Mean rating — top 20 drugs by review volume</div>
                  <div className="panel__subtitle">Patient rating on a 0–10 scale</div>
                </div>
              </div>
              <div className="panel__body">
                {ratingChart.length === 0 ? (
                  <EmptyState
                    title="No ratings"
                    message="No mean ratings were returned for the selected drugs."
                  />
                ) : (
                  <div className="reviews__chart-box">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={ratingChart}
                        layout="vertical"
                        margin={{ top: 4, right: 22, left: 4, bottom: 4 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                        <XAxis
                          type="number"
                          domain={[0, 10]}
                          tick={{ fill: "#94a3b8", fontSize: 11 }}
                          tickLine={false}
                          axisLine={{ stroke: "#1e293b" }}
                        />
                        <YAxis
                          type="category"
                          dataKey="drug"
                          width={120}
                          tick={{ fill: "#94a3b8", fontSize: 11 }}
                          tickLine={false}
                          axisLine={false}
                          tickFormatter={(value: string) =>
                            value.length > 17 ? `${value.slice(0, 16)}…` : value
                          }
                        />
                        <Tooltip content={<RatingTooltip />} cursor={{ fill: "rgba(34,211,238,0.06)" }} />
                        <Bar dataKey="mean_rating" name="Mean rating" radius={[0, 4, 4, 0]} barSize={13}>
                          {ratingChart.map((point, index, all) => (
                            <Cell
                              key={point.drug}
                              fill={point.mean_rating >= 7 ? "#4ade80" : point.mean_rating >= 5 ? "#22d3ee" : "#f59e0b"}
                              fillOpacity={Math.max(0.4, 1 - index * (0.5 / Math.max(1, all.length)))}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </section>

            <section className="panel">
              <div className="panel__head">
                <div>
                  <div className="panel__title">Top ADR terms across all drugs</div>
                  <div className="panel__subtitle">
                    Aggregated adverse-event mentions in reviews · top 25
                  </div>
                </div>
              </div>
              <div className="panel__body">
                {adrTerms.length === 0 ? (
                  <EmptyState
                    title="No ADR terms"
                    message="No adverse-event terms were extracted from reviews."
                  />
                ) : (
                  <div className="reviews__chart-box--terms">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={adrTerms}
                        layout="vertical"
                        margin={{ top: 4, right: 22, left: 4, bottom: 4 }}
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
                          dataKey="term"
                          width={120}
                          tick={{ fill: "#94a3b8", fontSize: 11 }}
                          tickLine={false}
                          axisLine={false}
                        />
                        <Tooltip content={<AdrTooltip />} cursor={{ fill: "rgba(34,211,238,0.06)" }} />
                        <Bar dataKey="count" name="Mentions" radius={[0, 4, 4, 0]} barSize={10}>
                          {adrTerms.map((point, index, all) => (
                            <Cell
                              key={point.term}
                              fill="#2dd4bf"
                              fillOpacity={Math.max(0.35, 1 - index * (0.65 / Math.max(1, all.length)))}
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
                <div className="panel__title">Review sentiment by drug</div>
                <div className="panel__subtitle">
                  {formatInt(drugs.length)} drugs · click a column header to re-sort · click a row
                  for the drug profile
                </div>
              </div>
            </div>
            <div className="panel__body panel__body--flush">
              <DataTable
                columns={columns}
                rows={drugs}
                rowKey={(d) => d.drug}
                initialSort={{ key: "reviews", direction: "desc" }}
                onRowClick={(d) => navigate(`/drug/${encodeURIComponent(d.drug)}`)}
              />
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
