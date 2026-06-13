import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchExplanation, generateSarDraft, submitDecision } from "../api/client";
import { PolicyFlagBadge, UboBadge } from "../components/Badges";
import { ScoreExplanationCard } from "../components/ScoreExplanationCard";
import type { Decision, ExplanationResponse, UboStatus } from "../types";
import { VERDICT_COLORS } from "../types";

const DECISIONS: { value: Decision; label: string; shortcut: string }[] = [
  { value: "CLEAR", label: "Clear Payment", shortcut: "C" },
  { value: "BLOCK", label: "Block Payment", shortcut: "B" },
  { value: "ESCALATE", label: "Escalate to Senior", shortcut: "E" },
  { value: "REQUEST_INFO", label: "Request More Info", shortcut: "R" },
  { value: "DEFER", label: "Defer 24h", shortcut: "D" },
];

export function CaseDetail() {
  const { paymentId } = useParams<{ paymentId: string }>();
  const navigate = useNavigate();
  const [explanation, setExplanation] = useState<ExplanationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [confirming, setConfirming] = useState<Decision | null>(null);
  const [sarDraft, setSarDraft] = useState<string | null>(null);

  useEffect(() => {
    if (!paymentId) return;
    fetchExplanation(paymentId)
      .then(setExplanation)
      .catch((err) => setError(String(err)));
  }, [paymentId]);

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center text-text-secondary">
        Could not load case {paymentId}: {error}
      </div>
    );
  }
  if (!explanation) {
    return <div className="flex flex-1 items-center justify-center text-text-secondary">Loading case…</div>;
  }

  const payment = explanation.payment ?? {};
  const entityRiskNode = explanation.tree.children.find((c) => c.id === "entity_risk_profile");
  const uboNode = entityRiskNode?.children?.find((c) => c.id === "ubo_resolution");
  const uboStatus = uboNode?.metadata?.ubo_resolution_status as UboStatus | undefined;
  const policyFlags = explanation.tree.children.filter((c) => c.id.startsWith("policy_flag:"));

  async function handleDecide(decision: Decision) {
    if (!paymentId) return;
    await submitDecision(paymentId, decision, "analyst@sokin.example", notes);
    setConfirming(null);
    navigate("/");
  }

  async function handleSarDraft() {
    if (!paymentId) return;
    const result = await generateSarDraft(paymentId, notes);
    setSarDraft(result.draft);
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel — payment instruction */}
        <div className="w-80 flex-shrink-0 overflow-y-auto border-r border-slate-700 p-4">
          <h2 className="mb-3 text-sm font-bold uppercase text-text-secondary">Payment Instruction</h2>
          <div className="font-mono-num mb-3 select-all text-lg text-text-primary">{explanation.payment_id}</div>

          <div className="mb-3 rounded border border-slate-700 p-3">
            <div className="text-xs uppercase text-text-secondary">Originator</div>
            <div className="text-text-primary">{payment.originator_name ?? "—"}</div>
            <div className="text-xs text-text-secondary">{payment.originator_country ?? "—"}</div>
            {uboStatus && (
              <div className="mt-2">
                <UboBadge status={uboStatus} />
              </div>
            )}
          </div>

          <div className="mb-3 rounded border border-slate-700 p-3">
            <div className="text-xs uppercase text-text-secondary">Beneficiary</div>
            <div className="text-text-primary">{payment.beneficiary_name ?? "—"}</div>
            <div className="text-xs text-text-secondary">{payment.beneficiary_country ?? "—"}</div>
          </div>

          <div className="mb-3 rounded border border-slate-700 p-3">
            <div className="text-xs uppercase text-text-secondary">Amount</div>
            <div className="font-mono-num text-lg text-text-primary">
              {payment.amount_usd ? `$${Number(payment.amount_usd).toLocaleString()}` : "—"}
            </div>
            <div className="text-xs text-text-secondary">{payment.asset_type ?? payment.chain ?? "Fiat"}</div>
          </div>

          {policyFlags.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {policyFlags.map((f) => (
                <PolicyFlagBadge key={f.id} flag={(f.metadata?.policy_flag as string) ?? f.id} />
              ))}
            </div>
          )}

          <div className="text-xs text-text-secondary">
            Screened at {new Date(explanation.screened_at).toLocaleString()}
          </div>
        </div>

        {/* Center panel — score breakdown */}
        <div className="flex-1 overflow-y-auto p-4">
          <ScoreExplanationCard explanation={explanation} />

          {explanation.network_context && (
            <div className="mt-4 rounded border border-slate-700 p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-text-primary">Network Cluster</span>
                {explanation.network_context.network_escalation_applied && (
                  <span className="rounded px-2 py-0.5 text-xs font-semibold" style={{ color: "#7C3AED", borderColor: "#7C3AED", borderWidth: 1 }}>
                    REVIEW ELEVATED
                  </span>
                )}
              </div>
              <div className="font-mono-num text-xs text-text-secondary">
                {explanation.network_context.neighbour_count} connected entities — network risk{" "}
                {explanation.network_context.network_risk_score.toFixed(2)}
              </div>
              <button
                type="button"
                onClick={() => navigate(`/network/${explanation.payment_id}`)}
                className="mt-2 rounded border border-slate-600 px-3 py-1.5 text-xs text-text-secondary hover:bg-bg"
              >
                Explore full network →
              </button>
            </div>
          )}
        </div>

        {/* Right panel — entity profile */}
        <div className="w-80 flex-shrink-0 overflow-y-auto border-l border-slate-700 p-4">
          <h2 className="mb-3 text-sm font-bold uppercase text-text-secondary">Entity Profile</h2>
          <div className="rounded border border-slate-700 p-3">
            <div className="text-text-primary">{payment.entity_name ?? explanation.payment_id}</div>
            <div className="mt-2 text-xs text-text-secondary">
              Track: <span className="text-text-primary">{explanation.track}</span>
            </div>
            <div className="mt-1 text-xs text-text-secondary">
              Composite score: <span className="font-mono-num text-text-primary">{explanation.composite_score.toFixed(3)}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={handleSarDraft}
            className="mt-3 w-full rounded border border-slate-600 px-3 py-2 text-sm text-text-secondary hover:bg-surface"
          >
            Generate SAR Draft
          </button>
          {sarDraft && (
            <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded border border-slate-700 bg-bg p-2 text-xs text-text-secondary">
              {sarDraft}
            </pre>
          )}
        </div>
      </div>

      {/* Action bar */}
      <div className="border-t border-slate-700 bg-surface p-3">
        <textarea
          className="mb-2 w-full rounded border border-slate-600 bg-bg p-2 text-sm text-text-primary"
          placeholder="Add analyst note…"
          rows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          {DECISIONS.map((d) => (
            <button
              key={d.value}
              type="button"
              onClick={() => setConfirming(d.value)}
              className="rounded px-4 py-2 text-sm font-semibold text-white"
              style={{
                backgroundColor:
                  d.value === "CLEAR"
                    ? VERDICT_COLORS.NO_MATCH
                    : d.value === "BLOCK"
                    ? VERDICT_COLORS.MATCH
                    : d.value === "ESCALATE"
                    ? "#7C3AED"
                    : "#334155",
              }}
            >
              {d.label} <span className="opacity-60">({d.shortcut})</span>
            </button>
          ))}
        </div>
        <div className="mt-2 text-xs text-text-secondary">
          Shortcuts: C = Clear · B = Block · E = Escalate · N = Add Note · ← → = Navigate cases
        </div>
      </div>

      {confirming && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-96 rounded-lg border border-slate-700 bg-surface p-4">
            <h3 className="mb-2 text-lg font-bold text-text-primary">Confirm: {confirming.replace("_", " ")}</h3>
            <p className="mb-3 text-sm text-text-secondary">
              This will record the decision for payment {explanation.payment_id} with the note below.
            </p>
            <textarea
              className="mb-3 w-full rounded border border-slate-600 bg-bg p-2 text-sm text-text-primary"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="rounded border border-slate-600 px-3 py-1.5 text-sm text-text-secondary"
                onClick={() => setConfirming(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded bg-accent px-3 py-1.5 text-sm font-semibold text-white"
                onClick={() => handleDecide(confirming)}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
