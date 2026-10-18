import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { ExternalLink } from "lucide-react";
import { api } from "../api/client";
import type { GeoPoint, Trial } from "../api/types";
import { useAsync, useDebouncedValue } from "../hooks/useAsync";
import { PageHeader } from "../components/PageHeader";
import { DataTable, type Column } from "../components/DataTable";
import { PhaseBadge, StatusBadge } from "../components/Badge";
import { EmptyState, ErrorState, Loader } from "../components/States";
import { Pagination } from "../components/Pagination";
import { formatDate, formatInt, joinCountries, statusTone, titleCase, TONE_COLORS } from "../utils/format";
import type { Tone } from "../utils/format";
import "./TrialsPage.css";

const PAGE_SIZE = 25;
const WORLD_CENTER: [number, number] = [25, 10];
const WORLD_ZOOM = 2;
const TILE_URL = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>';

/** Dominant (most frequent) trial status at a geo point. */
function dominantStatus(point: GeoPoint): string | null {
  const entries = Object.entries(point.statuses ?? {});
  if (entries.length === 0) return null;
  return entries.sort((a, b) => b[1] - a[1])[0][0];
}

/** Marker radius scales 3–18px by case count (square-root scale). */
function markerRadius(count: number, maxCount: number): number {
  if (maxCount <= 0) return 3;
  return Math.max(3, Math.min(18, 3 + Math.sqrt(count / maxCount) * 15));
}

function GeoTooltip({ point }: { point: GeoPoint }) {
  const status = dominantStatus(point);
  return (
    <div className="geo-tooltip">
      <div className="geo-tooltip__title">{formatInt(point.count)} trial locations</div>
      {status ? <div className="geo-tooltip__line">Dominant status: {titleCase(status)}</div> : null}
      {point.countries.length > 0 ? (
        <div className="geo-tooltip__line">{joinCountries(point.countries, 3)}</div>
      ) : null}
      {point.conditions.length > 0 ? (
        <div className="geo-tooltip__line">{joinCountries(point.conditions, 3)}</div>
      ) : null}
    </div>
  );
}

export function TrialsPage() {
  const [condition, setCondition] = useState("");
  const [status, setStatus] = useState("");
  const [phase, setPhase] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);

  const debouncedSearch = useDebouncedValue(search, 300);

  useEffect(() => {
    setOffset(0);
  }, [condition, status, phase, debouncedSearch]);

  const facets = useAsync(() => api.trialFacets(), []);

  const trials = useAsync(
    () =>
      api.trials({
        condition: condition || undefined,
        status: status || undefined,
        phase: phase || undefined,
        q: debouncedSearch.trim() || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    [condition, status, phase, debouncedSearch, offset],
  );

  // The map follows the condition filter (contract: /trials/geo?condition=…).
  const geo = useAsync(() => api.trialGeo(condition || undefined), [condition]);

  const maxCount = useMemo(
    () => (geo.data?.points ?? []).reduce((max, point) => Math.max(max, point.count), 0),
    [geo.data],
  );

  const columns: Column<Trial>[] = useMemo(
    () => [
      {
        key: "nct_id",
        header: "NCT ID",
        render: (trial) => (
          <a
            className="mono"
            href={`https://clinicaltrials.gov/study/${trial.nct_id}`}
            target="_blank"
            rel="noreferrer"
            onClick={(event) => event.stopPropagation()}
          >
            {trial.nct_id} <ExternalLink size={11} aria-hidden />
          </a>
        ),
      },
      {
        key: "title",
        header: "Title",
        wrap: true,
        render: (trial) => <span className="trials__title-cell">{trial.brief_title}</span>,
      },
      {
        key: "phase",
        header: "Phase",
        align: "center",
        render: (trial) => <PhaseBadge phase={trial.phase} />,
      },
      {
        key: "status",
        header: "Status",
        align: "center",
        render: (trial) => <StatusBadge status={trial.overall_status} />,
      },
      {
        key: "enrollment",
        header: "Enrollment",
        align: "right",
        render: (trial) => <span className="mono">{formatInt(trial.enrollment)}</span>,
      },
      {
        key: "countries",
        header: "Countries",
        render: (trial) => <span className="muted">{joinCountries(trial.countries, 2)}</span>,
      },
      {
        key: "dates",
        header: "Start → Completion",
        render: (trial) => (
          <span className="trials__date-range nowrap">
            {formatDate(trial.start_date)} → {formatDate(trial.completion_date)}
          </span>
        ),
      },
    ],
    [],
  );

  const total = trials.data?.total ?? 0;
  const points = geo.data?.points ?? [];

  return (
    <div className="page">
      <PageHeader
        title="Clinical Trials"
        subtitle="ClinicalTrials.gov studies with global site distribution — filter by condition, status and phase."
      />

      <div className="trials__layout">
        <section className="panel">
          <div className="panel__head">
            <div className="panel__title">Filters</div>
          </div>
          <div className="panel__body">
            {facets.error ? (
              <ErrorState
                message="Facets unavailable — filters are limited."
                onRetry={facets.reload}
              />
            ) : (
              <div className="trials__filters">
                <label className="field">
                  <span className="field__label">Condition</span>
                  <select
                    className="select"
                    value={condition}
                    onChange={(event) => setCondition(event.target.value)}
                    disabled={facets.loading}
                  >
                    <option value="">All conditions</option>
                    {(facets.data?.conditions ?? []).map((facet) => (
                      <option key={facet.value} value={facet.value}>
                        {facet.value} ({formatInt(facet.count)})
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span className="field__label">Status</span>
                  <select
                    className="select"
                    value={status}
                    onChange={(event) => setStatus(event.target.value)}
                    disabled={facets.loading}
                  >
                    <option value="">All statuses</option>
                    {(facets.data?.statuses ?? []).map((facet) => (
                      <option key={facet.value} value={facet.value}>
                        {titleCase(facet.value)} ({formatInt(facet.count)})
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span className="field__label">Phase</span>
                  <select
                    className="select"
                    value={phase}
                    onChange={(event) => setPhase(event.target.value)}
                    disabled={facets.loading}
                  >
                    <option value="">All phases</option>
                    {(facets.data?.phases ?? []).map((facet) => (
                      <option key={facet.value} value={facet.value}>
                        {titleCase(facet.value)} ({formatInt(facet.count)})
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span className="field__label">Search</span>
                  <input
                    type="search"
                    className="input input--search"
                    placeholder="Title, intervention, sponsor…"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                </label>

                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    setCondition("");
                    setStatus("");
                    setPhase("");
                    setSearch("");
                  }}
                >
                  Reset filters
                </button>
              </div>
            )}
          </div>
        </section>

        <div className="trials__map-wrap panel">
          <MapContainer
            center={WORLD_CENTER}
            zoom={WORLD_ZOOM}
            worldCopyJump
            scrollWheelZoom={false}
            className="trials-map"
          >
            <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
            {points.map((point, index) => {
              const status = dominantStatus(point);
              const color: Tone = status ? statusTone(status) : "cyan";
              return (
                <CircleMarker
                  key={`${point.lat.toFixed(3)}-${point.lon.toFixed(3)}-${index}`}
                  center={[point.lat, point.lon]}
                  radius={markerRadius(point.count, maxCount)}
                  pathOptions={{
                    color: TONE_COLORS[color],
                    fillColor: TONE_COLORS[color],
                    fillOpacity: 0.5,
                    weight: 1,
                  }}
                >
                  <Tooltip direction="top" offset={[0, -6]}>
                    <GeoTooltip point={point} />
                  </Tooltip>
                </CircleMarker>
              );
            })}
          </MapContainer>

          {geo.loading ? (
            <div className="trials__map-loading">
              <Loader label="Loading trial sites…" />
            </div>
          ) : null}

          {!geo.loading && !geo.error ? (
            <div className="trials__map-count">
              {formatInt(points.length)} site clusters · {formatInt(maxCount)} max per cluster
            </div>
          ) : null}

          {geo.error ? (
            <div className="trials__map-loading trials__map-loading--interactive">
              <ErrorState message={geo.error.message} onRetry={geo.reload} />
            </div>
          ) : null}
        </div>
      </div>

      <section className="panel">
        <div className="panel__head">
          <div>
            <div className="panel__title">Trials</div>
            <div className="panel__subtitle">
              <strong>{formatInt(total)}</strong> match{total === 1 ? "es" : ""} the current filters
              {condition ? ` · condition: ${condition}` : ""}
            </div>
          </div>
        </div>

        {trials.loading && trials.data === null ? (
          <Loader label="Loading trials…" />
        ) : trials.error ? (
          <ErrorState title="Could not load trials" message={trials.error.message} onRetry={trials.reload} />
        ) : (trials.data?.trials.length ?? 0) === 0 ? (
          <EmptyState
            title="No trials found"
            message="No ClinicalTrials.gov studies match the selected filters."
            action={
              <button
                type="button"
                className="btn"
                onClick={() => {
                  setCondition("");
                  setStatus("");
                  setPhase("");
                  setSearch("");
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
              rows={trials.data?.trials ?? []}
              rowKey={(trial) => trial.nct_id}
            />
            <Pagination offset={offset} limit={PAGE_SIZE} total={total} onChange={setOffset} />
          </>
        )}
      </section>
    </div>
  );
}
