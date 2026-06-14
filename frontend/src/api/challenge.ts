// Place at: frontend/src/api/challenge.ts
// Challenge System API client — does NOT modify the existing client.ts.

const BASE =
  (import.meta as any).env?.VITE_API_URL ?? "http://localhost:8001";

async function _post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ error: r.statusText }));
    throw new Error(err.error ?? r.statusText);
  }
  return r.json() as Promise<T>;
}

async function _get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ error: r.statusText }));
    throw new Error(err.error ?? r.statusText);
  }
  return r.json() as Promise<T>;
}

export interface SimilarCase {
  case_id: string;
  transaction_id: string;
  similarity_score: number;
  reviewer_verdict: "approved" | "blocked" | "escalated";
  review_timestamp: string | null;
  geopolitical_snapshot: Record<string, GeoContext>;
  summary: CaseSummary;
  contradicts_current: boolean;
}

export interface CaseSummary {
  entity_names: string[];
  amount: number;
  currency: string;
  typology_tags: string[];
  product_type: string;
  risk_scores: Record<string, number>;
  countries: string[];
  reviewer_rationale: string;
}

export interface GeoContext {
  FATF_status: "compliant" | "monitored" | "greylisted" | "blacklisted";
  basel_aml_index_score: number;
  active_sanctions_programs: string[];
  export_control_alerts: string[];
}

export interface ChallengeResult {
  challenge_id: string;
  challenge_text: string;
  current_case_summary: CaseSummary;
  similar_case_summary: CaseSummary;
  similarity_score: number;
}

export interface RecentCase {
  case_id: string;
  transaction_id: string;
  reviewer_verdict: string;
  review_timestamp: string | null;
  typology_tags: string[];
  has_challenges: boolean;
}

export const challengeApi = {
  submit: (transactionId: string, caseXml: string) =>
    _post<{ case_id: string }>("/api/cases/submit", {
      transaction_id: transactionId,
      case_xml: caseXml,
    }),

  findSimilar: (caseId: string) =>
    _get<SimilarCase[]>(`/api/cases/${encodeURIComponent(caseId)}/similar`),

  generateChallenge: (caseId: string, similarCaseId: string, reviewerDraftVerdict: string) =>
    _post<ChallengeResult>(`/api/cases/${encodeURIComponent(caseId)}/challenge`, {
      similar_case_id: similarCaseId,
      reviewer_draft_verdict: reviewerDraftVerdict,
    }),

  respond: (caseId: string, challengeId: string, reviewerResponse: string) =>
    _post<{ status: string }>(
      `/api/cases/${encodeURIComponent(caseId)}/challenge/${encodeURIComponent(challengeId)}/respond`,
      { reviewer_response: reviewerResponse },
    ),

  recent: () => _get<RecentCase[]>("/api/cases/recent"),
};
