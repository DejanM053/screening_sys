import type { Decision, ExplanationResponse, QueueItem, TransferType, UboStatus } from "../types";

const API_URL =
  import.meta.env.VITE_API_URL ?? import.meta.env.REACT_APP_API_URL ?? "http://localhost:8001";
const REVIEW_QUEUE_URL =
  import.meta.env.VITE_REVIEW_QUEUE_URL ??
  import.meta.env.REACT_APP_REVIEW_QUEUE_URL ??
  "http://localhost:8009";

async function getJson<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Request to ${url} failed with ${resp.status}`);
  }
  return (await resp.json()) as T;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw new Error(`Request to ${url} failed with ${resp.status}`);
  }
  return (await resp.json()) as T;
}

export interface QueueFilters {
  transferType?: TransferType;
  country?: string;
  minScore?: number;
  maxScore?: number;
  uboResolutionStatus?: UboStatus;
  assignedTo?: string;
}

export async function fetchQueue(filters: QueueFilters = {}): Promise<QueueItem[]> {
  const params = new URLSearchParams();
  if (filters.transferType) params.set("transfer_type", filters.transferType);
  if (filters.country) params.set("country", filters.country);
  if (filters.minScore !== undefined) params.set("min_score", String(filters.minScore));
  if (filters.maxScore !== undefined) params.set("max_score", String(filters.maxScore));
  if (filters.uboResolutionStatus) params.set("ubo_resolution_status", filters.uboResolutionStatus);
  if (filters.assignedTo) params.set("assigned_to", filters.assignedTo);

  const qs = params.toString();
  return getJson<QueueItem[]>(`${REVIEW_QUEUE_URL}/queue${qs ? `?${qs}` : ""}`);
}

export async function fetchExplanation(paymentId: string): Promise<ExplanationResponse> {
  return getJson<ExplanationResponse>(`${API_URL}/explanation/${encodeURIComponent(paymentId)}`);
}

export async function submitDecision(
  paymentId: string,
  decision: Decision,
  analystId: string,
  notes?: string
): Promise<{ payment_id: string; decision: Decision; requeued: boolean; item: QueueItem | null }> {
  return postJson(`${REVIEW_QUEUE_URL}/decide/${encodeURIComponent(paymentId)}`, {
    decision,
    analyst_id: analystId,
    notes,
  });
}

export async function generateSarDraft(
  paymentId: string,
  analystNotes?: string
): Promise<{ payment_id: string; draft: string }> {
  return postJson(`${API_URL}/generate-sar-draft`, {
    payment_id: paymentId,
    analyst_notes: analystNotes,
  });
}
