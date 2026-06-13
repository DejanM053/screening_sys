export type Verdict = "MATCH" | "REVIEW" | "NO_MATCH";

export type TransferType = "INTERNAL" | "OUTBOUND" | "INBOUND";

export type UboStatus = "FULL" | "PARTIAL" | "UNRESOLVED";

export type Decision = "CLEAR" | "BLOCK" | "ESCALATE" | "REQUEST_INFO" | "DEFER";

export interface ScoreNode {
  id: string;
  label: string;
  score: number | null;
  weight: number;
  weighted_contribution: number;
  detail: string;
  children: ScoreNode[];
  metadata: Record<string, unknown>;
}

export interface ConnectedEntity {
  id: string;
  score: number;
  shared_attribute?: string | null;
  hop_distance?: number | null;
}

export interface NetworkContext {
  neighbourhood_id: string;
  neighbour_count: number;
  network_risk_score: number;
  connected_entities: ConnectedEntity[];
  network_escalation_applied: boolean;
  escalation_reason?: string | null;
}

export interface PaymentInfo {
  payment_id?: string;
  originator_name?: string;
  originator_country?: string;
  originator_wallet?: string | null;
  beneficiary_name?: string;
  beneficiary_country?: string;
  beneficiary_wallet?: string | null;
  amount_usd?: number;
  asset_type?: string;
  chain?: string | null;
  entity_name?: string;
  [key: string]: unknown;
}

export interface ExplanationResponse {
  payment_id: string;
  verdict: Verdict;
  track: string;
  composite_score: number;
  tree: ScoreNode;
  network_context: NetworkContext | null;
  payment: PaymentInfo;
  llm_explanation: string | null;
  screened_at: string;
}

export interface QueueItem {
  payment_id: string;
  entity_id: string;
  entity_name: string;
  score: number;
  country?: string | null;
  lists_flagged: string[];
  transfer_type: TransferType;
  ubo_resolution_status: UboStatus;
  policy_flags: string[];
  network_risk_score: number;
  network_escalation_applied: boolean;
  amount_usd?: number | null;
  track?: string | null;
  enqueued_at: string;
  sla_deadline: string;
  status: "PENDING" | "DECIDED";
  high_priority: boolean;
  escalated: boolean;
  escalation_reason?: string | null;
  assigned_to?: string | null;
}

export const VERDICT_COLORS: Record<Verdict, string> = {
  MATCH: "#DC2626",
  REVIEW: "#D97706",
  NO_MATCH: "#16A34A",
};

export const UBO_COLOR = "#EA580C";
export const CLUSTER_COLOR = "#7C3AED";
export const INFO_COLOR = "#2563EB";
export const PENDING_COLOR = "#6B7280";
