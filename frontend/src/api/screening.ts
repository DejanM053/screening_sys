const QUEUE_URL = (import.meta as any).env?.VITE_REVIEW_QUEUE_URL ?? 'http://localhost:8009';
const API_URL = (import.meta as any).env?.VITE_API_URL ?? 'http://localhost:8001';

export interface QueueItem {
  payment_id: string;
  entity_id?: string;
  entity_name: string;
  score: number;
  country: string;
  lists_flagged?: string[];
  transfer_type?: string;
  ubo_resolution_status?: string;
  policy_flags?: string[];
  network_risk_score?: number;
  network_escalation_applied?: boolean;
  amount_usd?: number;
  track?: string;
  enqueued_at?: string;
  sla_deadline?: string;
  status?: string;
  high_priority?: boolean;
  escalated?: boolean;
  escalation_reason?: string | null;
  assigned_to?: string | null;
  decision?: string | null;
  decided_at?: string | null;
}

export interface ScoreNode {
  id: string;
  label: string;
  score: number | null;
  weight: number;
  weighted_contribution: number;
  detail: string;
  children: ScoreNode[];
  metadata: Record<string, any>;
}

export interface NetworkContext {
  neighbourhood_id: string;
  neighbour_count: number;
  network_risk_score: number;
  connected_entities: { id: string; score: number; shared_attribute?: string; hop_distance?: number }[];
  network_escalation_applied: boolean;
  escalation_reason: string | null;
}

export interface Explanation {
  payment_id: string;
  verdict: string;
  track: string;
  composite_score: number;
  tree: ScoreNode;
  network_context: NetworkContext | null;
  payment: Record<string, any>;
  llm_explanation: string | null;
  screened_at: string;
}

export const screeningApi = {
  getQueue: (): Promise<QueueItem[]> =>
    fetch(`${QUEUE_URL}/queue`)
      .then(r => r.ok ? r.json() : [])
      .catch(() => []),

  getDecidedQueue: (): Promise<QueueItem[]> =>
    fetch(`${QUEUE_URL}/queue?status=DECIDED`)
      .then(r => r.ok ? r.json() : [])
      .catch(() => []),

  getExplanation: (paymentId: string): Promise<Explanation | null> =>
    fetch(`${API_URL}/explanation/${encodeURIComponent(paymentId)}`)
      .then(r => r.ok ? r.json() : null)
      .catch(() => null),

  postDecision: (paymentId: string, decision: string, analystId = 'DM'): Promise<void> =>
    fetch(`${QUEUE_URL}/decide/${encodeURIComponent(paymentId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, analyst_id: analystId }),
    }).then(() => {}),

  enqueueCase: (item: {
    payment_id: string; entity_name: string; score: number;
    country: string; transfer_type: string; ubo_resolution_status: string;
    policy_flags: string[]; amount_usd: number; track: string;
  }): Promise<void> =>
    fetch(`${QUEUE_URL}/enqueue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...item, entity_id: item.payment_id }),
    }).then(() => {}),
};
