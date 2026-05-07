export type Organization = {
  id: string;
  name: string;
  short_name?: string | null;
  organization_type: string;
  created_at: string;
  updated_at: string;
};

export type MemberItem = {
  id: string;
  organization_id: string;
  user_id: string;
  role: string;
  status: string;
  email: string;
  full_name: string;
};

export type Dashboard = {
  organization_id: string;
  organization_name: string;
  active_reports: number;
  reports_awaiting_approval: number;
  processed_documents: number;
  total_requirements: number;
  high_risks: number;
  readiness_percent: number;
  unread_notifications: number;
};

export type DocumentItem = {
  id: string;
  file_name: string;
  category: string;
  status: string;
  processed_at?: string | null;
  created_at: string;
};

export type DocumentSearchMatch = {
  fragment_id: string;
  document_id: string;
  document_name: string;
  fragment_text: string;
  score: number;
  keyword_score?: number | null;
  vector_score?: number | null;
  page_number?: number | null;
  sheet_name?: string | null;
};

export type ReportItem = {
  id: string;
  title: string;
  report_type: string;
  status: string;
  readiness_percent: number;
  created_at: string;
};

export type ReportMatrixRow = {
  requirement_id: string;
  category: string;
  title: string;
  text: string;
  applicability_status: string;
  source_document_name?: string | null;
  source_fragment_text?: string | null;
  required_data: string[];
  found_data: string[];
  evidence: Array<{
    document_name?: string | null;
    fragment_text: string;
    confidence_score: number;
  }>;
  status: string;
  confidence_score: number;
  risk_level: string;
  system_comment?: string | null;
  user_comment?: string | null;
  included_in_report: boolean;
};

export type RequirementItem = {
  id: string;
  organization_id: string;
  report_id?: string | null;
  title: string;
  category: string;
  text: string;
  applicability_status: string;
  applicability_reason?: string | null;
  required_data: string[];
  found_data: string[];
  status: string;
  confidence_score: number;
  risk_level: string;
  user_comment?: string | null;
};

export type RiskItem = {
  id: string;
  report_id?: string | null;
  requirement_id?: string | null;
  title: string;
  description: string;
  risk_level: string;
  status: string;
  recommended_action?: string | null;
  assigned_to_id?: string | null;
};

export type ReportSection = {
  id: string;
  title: string;
  content: string;
  status: string;
  order_number: number;
};

export type Explanation = {
  id: string;
  conclusion: string;
  explanation_text: string;
  confidence_score: number;
  risk_level: string;
  logic_json: string[];
  evidence_json: Array<{
    document_id?: string | null;
    fragment_id?: string | null;
    description: string;
  }>;
  source_document_id?: string | null;
  source_fragment_id?: string | null;
  recommended_action?: string | null;
};

export type ExportFile = {
  id: string;
  file_name: string;
  export_type: string;
  storage_path: string;
  status: string;
};

export type ReportVersion = {
  id: string;
  organization_id: string;
  report_id: string;
  version_number: number;
  created_by_id?: string | null;
  report_status: string;
  title: string;
  report_type: string;
  readiness_percent: number;
  comment?: string | null;
  sections_json: Array<{
    id: string;
    title: string;
    content: string;
    order_number: number;
    status: string;
    source_requirement_ids: string[];
  }>;
  matrix_json: Array<Record<string, unknown>>;
  explanations_json: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
};

export type NotificationItem = {
  id: string;
  organization_id?: string | null;
  user_id?: string | null;
  title: string;
  body: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type AuditLogItem = {
  id: string;
  organization_id?: string | null;
  user_id?: string | null;
  user_email?: string | null;
  user_full_name?: string | null;
  entity_type: string;
  entity_id?: string | null;
  action: string;
  details: Record<string, unknown>;
  created_at: string;
};
