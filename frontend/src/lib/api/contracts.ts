export interface AgencyOption {
  id?: string;
  agency_id?: string;
  code: string;
  name: string;
}

interface DefinitionOption {
  code: string;
  label: string;
  description?: string;
  available?: boolean;
}

interface EmployeeOption {
  id: string;
  display_name: string;
  role: "gp" | "ca";
  agency_id: string;
  identity_status: "controlled" | "masked" | string;
}

export interface AnalyticsMetadata {
  agencies: AgencyOption[];
  employees?: {
    gp: EmployeeOption[];
    ca: EmployeeOption[];
  };
  statuses?: DefinitionOption[];
  intervals?: DefinitionOption[];
  roles?: DefinitionOption[];
  definitions?: DefinitionOption[] | Record<string, unknown>;
  date_range?: { min?: string | null; max?: string | null };
  [key: string]: unknown;
}

export interface CompletenessLimitation {
  code?: string;
  message: string;
}

export interface AnalyticsCompleteness {
  provisional?: boolean;
  observed_records?: number;
  registered_requests?: number;
  funded_requests?: number;
  matched_requests?: number;
  matched_without_financed_status?: number;
  tb2_only_records?: number;
  tb2_only_observations?: number;
  future_date_count?: number;
  date_anomaly_count?: number;
  date_anomaly_records?: number;
  future_request_date_records?: number;
  future_milestone_date_records?: number;
  expected_agency_months?: number;
  tb1_submitted_agency_months?: number;
  tb1_usable_agency_months?: number;
  tb1_unusable_submitted_agency_months?: number;
  missing_tb1_agency_months?: number;
  tb1_submission_coverage_rate?: number | null;
  tb1_usable_coverage_rate?: number | null;
  source_coverage?: string | Record<string, unknown>;
  has_tb1_data?: boolean;
  has_tb2_data?: boolean;
  typed_staging?: {
    tb1?: TypedStagingCompleteness;
    tb2?: TypedStagingCompleteness;
  };
  limitations?: Array<string | CompletenessLimitation>;
  [key: string]: unknown;
}

export interface TypedStagingCompleteness {
  committed_rows?: number;
  quarantined_rows?: number;
  submitted_agency_months?: number;
  usable_agency_months?: number;
}

export type AnalyticsRecord = Record<string, unknown>;

export interface AnalyticsResultsResponse<T = AnalyticsRecord> {
  filters?: Record<string, unknown>;
  completeness?: AnalyticsCompleteness;
  results: T[];
}

export interface OverviewResponse {
  filters?: Record<string, unknown>;
  completeness?: AnalyticsCompleteness;
  summary: AnalyticsRecord;
  trends?: AnalyticsRecord[];
  [key: string]: unknown;
}

export interface DelaysResponse {
  filters?: Record<string, unknown>;
  completeness?: AnalyticsCompleteness;
  intervals: AnalyticsRecord[];
  aging: AnalyticsRecord[];
}

export interface ImportBatch {
  id: string;
  original_filename: string | null;
  workbook_type: string;
  status: "uploaded" | "queued" | "processing" | "completed" | "partial" | "failed";
  file_size: number;
  discovered_count: number;
  valid_staged_count: number;
  quarantined_count: number;
  unmatched_count: number;
  published_or_updated_count: number;
  checksum_sha256?: string;
  reporting_period?: string | null;
  schema_version?: number;
  sheet_count?: number;
  detected_agency?: AgencyOption | null;
  created_at: string;
  started_at?: string | null;
  finished_at: string | null;
  failure_code?: string;
  error_message: string;
  duplicate?: boolean;
}

export interface DataQualityIssue {
  id: string;
  severity: "info" | "warning" | "error";
  code: string;
  field_name: string;
  field_label: string;
  message: string;
  user_title: string;
  required_correction: string;
  submitted_value: string | null;
  expected_format: string;
  row_values: Array<{
    field_name: string;
    field_label: string;
    value: string | null;
  }>;
  action_kind: "reference_ca" | "reference_gp" | "template" | "matching" | string;
  sheet_name: string | null;
  source_row: number | null;
  created_at: string;
}

export interface CreditRequestStatus {
  id: string;
  code: string;
  label: string;
  pipeline_stage: string;
  is_terminal: boolean;
  is_financed: boolean;
  is_rejected: boolean;
}

export interface CreditRequest {
  id: string;
  public_id?: string;
  agency: AgencyOption;
  display_reference?: string;
  reference?: string;
  client_name?: string;
  client_identifier?: string;
  phone?: string;
  address?: string;
  amount: string | null;
  credit_type: string;
  request_type?: string;
  activity_category: string;
  request_date: string | null;
  received_at_agency_date?: string | null;
  assigned_to_gp_date?: string | null;
  counsellor_name?: string;
  gp_name?: string;
  visit_date?: string | null;
  disbursement_date: string | null;
  rejection_date: string | null;
  missing_from_latest_tb2_period?: string | null;
  status: CreditRequestStatus | null;
  rejection_reason?: { id: string; code: string; label: string; category: string } | null;
  comments?: string;
  source_completeness: CreditRequestSourceCompleteness;
  history_scope?: "current_provenance" | string;
  source_history?: ApplicationHistoryRecord[];
  status_history?: CreditRequestStatusHistory[];
  created_at?: string;
  updated_at: string;
}

export interface CreditRequestStatusHistory {
  id: string;
  status_code: string;
  status_label: string;
  effective_date: string;
  source_tb1_row_id: string | null;
  source_tb2_row_id: string | null;
  created_at: string;
}

export interface CreditRequestSourceCompleteness {
  matched: boolean;
}

export interface ApplicationHistoryRecord {
  id: string;
  batch_id: string;
  original_filename: string | null;
  source_kind: string;
  reporting_period?: string | null;
  sheet_name: string | null;
  source_row: number;
  row_status: string;
  source_class_authoritative: boolean;
  controls_current_state: boolean;
  created_at: string;
  [key: string]: unknown;
}

export interface CurrentUser {
  id: string;
  username: string;
  capabilities: {
    can_import: boolean;
    can_manage_reference_data?: boolean;
    can_view_all_agencies: boolean;
    can_view_client_pii: boolean;
    can_approve_mappings: boolean;
    credit_request_scope: "all" | "agency" | "assigned" | "none";
  };
}

export interface AssistantConversationMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantSource {
  type: string;
  label: string;
  detail?: string;
}

export interface AssistantResponse {
  answer: string;
  sources: AssistantSource[];
  links: Array<{ label: string; url: string }>;
  suggestions: string[];
}

export interface ReferenceAgency {
  id: string;
  name: string;
  code: string | null;
  is_active: boolean;
  usage_count?: number;
}

export interface ReferenceEmployee {
  id: string;
  name: string;
  email: string;
  agency_id: string;
  role: "ca" | "gp";
  is_active: boolean;
  usage_count?: number;
}

export interface ReferenceDimension {
  id: string;
  name: string;
  is_active: boolean;
  usage_count: number;
}

export interface OperationalReferenceData {
  agencies: ReferenceAgency[];
  employees: {
    ca: ReferenceEmployee[];
    gp: ReferenceEmployee[];
  };
  dimensions: Record<string, ReferenceDimension[]>;
}

export interface AuthTokenResponse {
  access: string;
  access_expires_in: number;
}
