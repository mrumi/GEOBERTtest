// ============================================================
// lib/types.ts — Types mirroring api/schemas.py exactly
// ============================================================
// Kept 1:1 with the backend Pydantic models so a schema change
// on the backend surfaces as a TypeScript error here instead of
// a silent runtime mismatch.

export interface StudyResult {
  gse_id: string;
  relevance_score: number; // 0-1, sigmoid-normalized
  geo_link: string;
  organism: string;
  tissue: string;
  assay_type: string;
  library_strategy: string;
  fields_found: string[];
  is_superseries: boolean;
  is_subseries: boolean;
  parent_series_id: string;
  subseries_ids: string[];
}

export interface SampleResult {
  gse_id: string;
  gsm_id: string;
  relevance_score: number | null;
  title: string;
  organism: string;
  library_strategy: string;
  cell_line: string;
  cell_type: string;
  tissue: string;
  disease: string;
  genotype: string;
}

export interface PlatformDistributionEntry {
  name: string;
  count: number;
  percent: number;
}

export interface StatsOverview {
  dataset_count: number;
  sample_count: number;
  platform_count: number;
  tissue_count: number;
  platform_distribution: PlatformDistributionEntry[];
}

export interface RelevanceQuality {
  query_match: number | null; // 0-1, or null = "N/A"
  metadata_match: number | null; // 0-1, or null = "N/A"
}

export interface DashboardStats {
  stats_overview: StatsOverview;
  relevance_quality: RelevanceQuality;
  top_fields_matched: string[];
}

export interface QueryResponse {
  session_id: string;
  query: string;
  answer: string;
  intent: string;
  query_type: string;
  strategy: string;
  filters: Record<string, string>;
  dropped_filters: Record<string, string>;
  top_gse_ids: string[];
  studies: StudyResult[];
  samples: SampleResult[];
  dashboard_stats: DashboardStats;
}

export interface MessageOut {
  role: "user" | "assistant";
  content: string;
  query_info: Record<string, unknown> | null;
  dropped_filters: Record<string, string> | null;
  top_gse_ids: string[] | null;
  studies: StudyResult[] | null;
  samples: SampleResult[] | null;
  dashboard_stats: DashboardStats | null;
  created_at: string;
}

export interface SessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail extends SessionSummary {
  messages: MessageOut[];
}

export interface DatasetDetail {
  gse_id: string;
  geo_link: string;
  organism: string;
  tissue: string;
  assay_type: string;
  library_strategy: string;
  instrument_model: string;
  bioproject_url: string;
  fields: Record<string, string>;
  sample_count: number;
  samples: SampleResult[];
  is_superseries: boolean;
  is_subseries: boolean;
  parent_series_id: string;
  subseries_ids: string[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export type UserRole = "researcher" | "clinician" | "student" | "admin";

export interface RegisterPayload {
  full_name: string;
  username: string;
  email: string;
  password: string;
  role: UserRole;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface UserOut {
  id: string;
  full_name: string;
  username: string;
  email: string;
  role: string;
  created_at: string;
}
