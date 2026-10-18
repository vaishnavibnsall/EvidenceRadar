/**
 * Thin fetch client for the EvidenceRadar REST API (see docs/api.md).
 * All requests are same-origin `/api/...` — in dev the Vite proxy forwards
 * them to the FastAPI backend on :8000.
 */
import type {
  DrugDetail,
  DrugQuery,
  DrugsResponse,
  GeoResponse,
  Health,
  Methodology,
  Overview,
  ReactionDetail,
  ReviewStatsQuery,
  ReviewStatsResponse,
  SignalQuery,
  SignalsResponse,
  TrialFacets,
  TrialQuery,
  TrialsResponse,
} from "./types";

const BASE_URL = "/api";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type QueryParams = Record<string, string | number | boolean | null | undefined>;

function buildUrl(path: string, params?: QueryParams): string {
  const search = new URLSearchParams();
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null || value === "") continue;
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return `${BASE_URL}${path}${qs ? `?${qs}` : ""}`;
}

async function request<T>(path: string, params?: QueryParams): Promise<T> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path, params), {
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError("Could not reach the EvidenceRadar API — is the backend running?", 0);
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body?.detail === "string" && body.detail.trim() !== "") {
        detail = body.detail;
      }
    } catch {
      /* error body was not JSON — keep the generic message */
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<Health>("/health"),

  overview: () => request<Overview>("/overview"),

  signals: (query: SignalQuery = {}) =>
    request<SignalsResponse>("/signals", {
      min_cases: query.min_cases,
      min_score: query.min_score,
      q: query.q,
      sort: query.sort,
      limit: query.limit,
      offset: query.offset,
    }),

  drugs: (query: DrugQuery = {}) =>
    request<DrugsResponse>("/drugs", {
      q: query.q,
      sort: query.sort,
      limit: query.limit,
      offset: query.offset,
    }),

  drug: (name: string) => request<DrugDetail>(`/drugs/${encodeURIComponent(name)}`),

  reaction: (pt: string) => request<ReactionDetail>(`/reactions/${encodeURIComponent(pt)}`),

  trials: (query: TrialQuery = {}) =>
    request<TrialsResponse>("/trials", {
      condition: query.condition,
      status: query.status,
      phase: query.phase,
      q: query.q,
      limit: query.limit,
      offset: query.offset,
    }),

  trialGeo: (condition?: string) =>
    request<GeoResponse>("/trials/geo", { condition: condition || undefined }),

  trialFacets: () => request<TrialFacets>("/trials/facets"),

  reviewStats: (query: ReviewStatsQuery = {}) =>
    request<ReviewStatsResponse>("/reviews/stats", {
      limit: query.limit,
      sort: query.sort,
    }),

  methodology: () => request<Methodology>("/methodology"),
};
