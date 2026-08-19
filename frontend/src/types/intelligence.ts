export type IntelligenceStepStatus = "completed" | "attention" | "queued";

export interface IntelligenceTimelineStep {
  key: string;
  label: string;
  status: IntelligenceStepStatus;
  detail: string;
}

export interface IntelligenceOrderSummary {
  id: string;
  ticket_number: string | null;
  commission_number: string | null;
  delivery_week: string | null;
  status: string;
  item_count: number;
  issue_count: number;
}

export interface OrderIntelligenceResult {
  duplicate: boolean;
  email_id: string;
  subject: string;
  sender_email: string;
  classification: string;
  client_profile: string | null;
  client_name: string | null;
  client_confidence: number;
  client_evidence: string[];
  next_action: string;
  reference_codes: string[];
  notes: string[];
  attachments: Array<{
    file_name: string;
    is_scanned: boolean;
    processing_status: string;
  }>;
  orders: IntelligenceOrderSummary[];
  requires_review: boolean;
  clarification_draft: string | null;
  timeline: IntelligenceTimelineStep[];
}
