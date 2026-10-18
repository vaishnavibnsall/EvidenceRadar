/**
 * Types mirroring the EvidenceRadar REST contract (docs/api.md) exactly.
 * Nullable fields are typed `| null` — floats may be null when not computable.
 */

/* ------------------------------------------------------------------ health */

export interface Health {
  status: string;
  database: boolean;
  signals: number;
  version: string;
}

/* ---------------------------------------------------------------- overview */

export interface MonthCases {
  month: string;
  cases: number;
}

export interface TopDrug {
  drug: string;
  cases: number;
}

export interface Overview {
  cases: number;
  unique_drugs: number;
  unique_reactions: number;
  trials: number;
  reviews: number;
  signals: number;
  strong_signals: number;
  drug_pairs: number;
  date_range: { from: string; to: string };
  global_trend: MonthCases[];
  top_drugs: TopDrug[];
  source: string;
  last_refresh: string;
}

/* ----------------------------------------------------------------- signals */

export interface Signal {
  drug: string;
  reaction: string;
  cases: number;
  drug_cases: number;
  reaction_cases: number;
  total_cases: number;
  expected: number | null;
  prr: number | null;
  prr_lo: number | null;
  prr_hi: number | null;
  ror: number | null;
  ror_lo: number | null;
  ror_hi: number | null;
  chi2: number | null;
  p_value: number | null;
  ic: number | null;
  ebgm: number | null;
  eb05: number | null;
  in_label: boolean;
  first_seen: string | null;
  last_seen: string | null;
  trend_slope: number | null;
  evidence_score: number | null;
}

export type SignalSort = "evidence_score" | "cases" | "ror" | "eb05" | "p_value";

export interface SignalQuery {
  min_cases?: number;
  min_score?: number;
  q?: string;
  sort?: SignalSort;
  limit?: number;
  offset?: number;
}

export interface SignalsResponse {
  total: number;
  signals: Signal[];
}

/* ------------------------------------------------------------------- drugs */

export interface DrugListItem {
  drug: string;
  cases: number;
  reactions: number;
  top_reaction: string | null;
  top_reaction_cases: number | null;
  max_score: number | null;
  trials: number;
  reviews: number;
  mean_rating: number | null;
  label_present: boolean;
}

export type DrugSort = "cases" | "max_score" | "reviews" | "trials";

export interface DrugQuery {
  q?: string;
  limit?: number;
  offset?: number;
  sort?: DrugSort;
}

export interface DrugsResponse {
  total: number;
  drugs: DrugListItem[];
}

export interface DrugReaction {
  reaction: string;
  cases: number;
  prr: number | null;
  ror: number | null;
  ror_lo: number | null;
  eb05: number | null;
  ic: number | null;
  evidence_score: number | null;
  in_label: boolean;
  trend_slope: number | null;
}

export interface DrugPair {
  drug: string;
  co_reports: number;
  lift: number | null;
}

export interface AdrTerm {
  term: string;
  count: number;
}

export interface DrugReviews {
  reviews: number;
  mean_rating: number | null;
  low_rating_share: number | null;
  neg_share: number | null;
  pos_share: number | null;
  adr_terms: AdrTerm[];
}

export interface DrugLabel {
  has_label: boolean;
  brand_name: string | null;
  generic_name: string | null;
  indications: string | null;
  adverse_reactions: string | null;
  warnings: string | null;
  boxed_warning: boolean;
  source_url: string | null;
}

export interface DrugTrial {
  nct_id: string;
  brief_title: string;
  overall_status: string;
  phase: string;
  enrollment: number | null;
  conditions: string[];
}

export interface DrugDetail {
  drug: string;
  summary: DrugListItem;
  reactions: DrugReaction[];
  trend: MonthCases[];
  pairs: DrugPair[];
  reviews: DrugReviews | null;
  label: DrugLabel | null;
  trials: DrugTrial[];
}

/* --------------------------------------------------------------- reactions */

export interface ReactionDrug {
  drug: string;
  cases: number;
  ror: number | null;
  eb05: number | null;
  evidence_score: number | null;
}

export interface ReactionDetail {
  reaction: string;
  total_cases: number;
  drugs: ReactionDrug[];
  monthly: MonthCases[];
}

/* ------------------------------------------------------------------ trials */

export interface Trial {
  nct_id: string;
  brief_title: string;
  overall_status: string;
  phase: string;
  conditions: string[];
  interventions: string[];
  sponsor: string | null;
  enrollment: number | null;
  start_date: string | null;
  completion_date: string | null;
  study_type: string | null;
  location_count: number;
  countries: string[];
}

export interface TrialQuery {
  condition?: string;
  status?: string;
  phase?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface TrialsResponse {
  total: number;
  trials: Trial[];
}

export interface GeoPoint {
  lat: number;
  lon: number;
  count: number;
  countries: string[];
  conditions: string[];
  statuses: Record<string, number>;
}

export interface GeoResponse {
  points: GeoPoint[];
}

export interface Facet {
  value: string;
  count: number;
}

export interface TrialFacets {
  statuses: Facet[];
  phases: Facet[];
  conditions: Facet[];
}

/* ----------------------------------------------------------------- reviews */

export interface ReviewStat {
  drug: string;
  reviews: number;
  mean_rating: number | null;
  low_rating_share: number | null;
  neg_share: number | null;
  pos_share: number | null;
  adr_terms: AdrTerm[];
}

export type ReviewSort = "reviews" | "mean_rating" | "low_rating_share";

export interface ReviewStatsQuery {
  limit?: number;
  sort?: ReviewSort;
}

export interface ReviewStatsResponse {
  drugs: ReviewStat[];
}

/* -------------------------------------------------------------- methodology */

export interface DisproportionalityMeasure {
  title: string;
  formula: string;
  description: string;
}

export interface Scoring {
  weights: Record<string, number>;
  label_penalty: number;
  formula: string;
}

export interface Source {
  name: string;
  url: string;
  description: string;
  records: string;
}

export interface Methodology {
  disproportionality: DisproportionalityMeasure[];
  scoring: Scoring;
  sources: Source[];
  limitations: string[];
}
