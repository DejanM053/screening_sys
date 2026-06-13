import { useEffect, useState } from "react";
import { fetchQueue, submitDecision } from "../api/client";
import { PolicyFlagBadge, TransferTypeBadge, UboBadge } from "../components/Badges";
import { ScoreExplanationCard } from "../components/ScoreExplanationCard";
import { fetchExplanation } from "../api/client";
import type { Decision, ExplanationResponse, QueueItem } from "../types";
import { VERDICT_COLORS } from "../types";

export function MobileApproval() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [selected, setSelected] = useState<QueueItem | null>(null);
  const [explanation, setExplanation] = useState<ExplanationResponse | null>(null);
  const [confirming, setConfirming] = useState<Decision | null>(null);
  const [pin, setPin] = useState("");

  useEffect(() => {
    fetchQueue({ minScore: 0.85 }).then((data) => setItems(data.filter((i) => i.high_priority || i.escalated)));
  }, []);

  useEffect(() => {
    if (!selected) {
      setExplanation(null);
      return;
    }
    fetchExplanation(selected.payment_id).then(setExplanation).catch(() => setExplanation(null));
  }, [selected]);

  async function confirmDecision(decision: Decision) {
    if (!selected || pin.length < 4) return;
    await submitDecision(selected.payment_id, decision, "senior-analyst@sokin.example");
    setConfirming(null);
    setPin("");
    setSelected(null);
    setItems((prev) => prev.filter((i) => i.payment_id !== selected.payment_id));
  }

  return (
    <div className="mx-auto flex h-full w-full max-w-[375px] flex-col overflow-hidden border-x border-slate-700 bg-bg">
      {!selected && (
        <div className="flex-1 overflow-y-auto p-4">
          <h1 className="mb-3 text-lg font-bold text-text-primary">Urgent Reviews</h1>
          {items.length === 0 && <div className="text-sm text-text-secondary">No urgent escalations.</div>}
          {items.map((item) => (
            <button
              key={item.payment_id}
              onClick={() => setSelected(item)}
              className="mb-3 w-full rounded-lg border p-4 text-left"
              style={{ borderColor: VERDICT_COLORS.REVIEW, backgroundColor: `${VERDICT_COLORS.REVIEW}1A` }}
            >
              <div className="text-sm font-bold uppercase" style={{ color: VERDICT_COLORS.REVIEW }}>
                Urgent: Payment Review Required
              </div>
              <div className="mt-2 text-text-primary">{item.entity_name}</div>
              <div className="font-mono-num mt-1 text-2xl text-text-primary">
                ${item.amount_usd?.toLocaleString() ?? "—"}
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <TransferTypeBadge type={item.transfer_type} />
                {item.ubo_resolution_status === "UNRESOLVED" && <UboBadge status="UNRESOLVED" />}
                {item.policy_flags.map((f) => (
                  <PolicyFlagBadge key={f} flag={f} />
                ))}
              </div>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="flex-1 overflow-y-auto p-4">
          <button onClick={() => setSelected(null)} className="mb-3 text-sm text-text-secondary">
            ← Back
          </button>

          <div
            className="mb-3 rounded-lg border p-4"
            style={{ borderColor: VERDICT_COLORS.REVIEW, backgroundColor: `${VERDICT_COLORS.REVIEW}1A` }}
          >
            <div className="text-sm font-bold uppercase" style={{ color: VERDICT_COLORS.REVIEW }}>
              Urgent: Payment Review Required
            </div>
            <div className="mt-2 text-sm text-text-secondary">Sending</div>
            <div className="text-text-primary">{explanation?.payment.originator_name ?? "—"}</div>
            <div className="mt-2 text-sm text-text-secondary">Receiving</div>
            <div className="flex items-center gap-2 text-text-primary">
              {explanation?.payment.beneficiary_name ?? selected.entity_name}
              {selected.ubo_resolution_status === "UNRESOLVED" && <UboBadge status="UNRESOLVED" />}
            </div>
            <div className="mt-2 text-sm text-text-secondary">Transfer type</div>
            <TransferTypeBadge type={selected.transfer_type} />
            <div className="mt-2 text-sm text-text-secondary">Chain / Token</div>
            <div className="text-text-primary">
              {explanation?.payment.chain ?? "—"} / {explanation?.payment.asset_type ?? "—"}
            </div>
            <div className="font-mono-num mt-2 text-3xl text-text-primary">
              ${selected.amount_usd?.toLocaleString() ?? "—"}
            </div>
            {selected.policy_flags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {selected.policy_flags.map((f) => (
                  <PolicyFlagBadge key={f} flag={f} />
                ))}
              </div>
            )}
          </div>

          {explanation && (
            <>
              <div className="mb-3">
                <ScoreExplanationCard explanation={explanation} size="compact" />
              </div>
              {explanation.llm_explanation && (
                <p className="mb-3 text-xs text-text-secondary">{explanation.llm_explanation}</p>
              )}
            </>
          )}

          <div className="flex flex-col gap-2">
            <button
              onClick={() => setConfirming("BLOCK")}
              className="rounded py-3 text-sm font-semibold text-white"
              style={{ backgroundColor: VERDICT_COLORS.MATCH }}
            >
              BLOCK
            </button>
            <button
              onClick={() => setConfirming("CLEAR")}
              className="rounded py-3 text-sm font-semibold text-white"
              style={{ backgroundColor: VERDICT_COLORS.NO_MATCH }}
            >
              CLEAR
            </button>
            <button
              onClick={() => setConfirming("ESCALATE")}
              className="rounded py-3 text-sm font-semibold text-white"
              style={{ backgroundColor: "#7C3AED" }}
            >
              ESCALATE
            </button>
          </div>
        </div>
      )}

      {confirming && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
          <div className="w-72 rounded-lg border border-slate-700 bg-surface p-4">
            <h3 className="mb-2 text-base font-bold text-text-primary">Confirm {confirming}</h3>
            <p className="mb-3 text-xs text-text-secondary">Enter your PIN to confirm this decision.</p>
            <input
              type="password"
              inputMode="numeric"
              maxLength={6}
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              className="mb-3 w-full rounded border border-slate-600 bg-bg p-2 text-center text-lg text-text-primary"
              placeholder="••••"
            />
            <div className="flex justify-end gap-2">
              <button
                className="rounded border border-slate-600 px-3 py-1.5 text-sm text-text-secondary"
                onClick={() => {
                  setConfirming(null);
                  setPin("");
                }}
              >
                Cancel
              </button>
              <button
                className="rounded bg-accent px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                disabled={pin.length < 4}
                onClick={() => confirmDecision(confirming)}
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
