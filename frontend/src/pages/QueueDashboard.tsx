import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchQueue } from "../api/client";
import { PolicyFlagBadge, SlaBadge, TransferTypeBadge, VerdictBadge } from "../components/Badges";
import type { QueueItem, TransferType, UboStatus, Verdict } from "../types";
import { VERDICT_COLORS } from "../types";

function verdictFromTrack(item: QueueItem): Verdict {
  if (item.track?.startsWith("A:") && item.track !== "A:partial") return "MATCH";
  return "REVIEW";
}

export function QueueDashboard() {
  const navigate = useNavigate();
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [transferType, setTransferType] = useState<TransferType | "">("");
  const [minScore, setMinScore] = useState(0.5);
  const [country, setCountry] = useState("");
  const [uboStatus, setUboStatus] = useState<UboStatus | "">("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchQueue({
      transferType: transferType || undefined,
      minScore,
      country: country || undefined,
      uboResolutionStatus: uboStatus || undefined,
    })
      .then((data) => {
        if (!cancelled) {
          setItems(
            [...data].sort(
              (a, b) => b.score - a.score || new Date(a.sla_deadline).getTime() - new Date(b.sla_deadline).getTime()
            )
          );
        }
      })
      .catch((err) => !cancelled && setError(String(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [transferType, minScore, country, uboStatus]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="border-b border-slate-700 bg-surface px-6 py-4">
        <h1 className="text-xl font-bold text-text-primary">Review Queue</h1>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            Min score
            <input
              type="range"
              min={0.5}
              max={1}
              step={0.01}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
            />
            <span className="font-mono-num">{minScore.toFixed(2)}</span>
          </label>

          <select
            className="rounded border border-slate-600 bg-bg px-2 py-1 text-sm text-text-primary"
            value={transferType}
            onChange={(e) => setTransferType(e.target.value as TransferType | "")}
          >
            <option value="">All transfer types</option>
            <option value="INTERNAL">Internal</option>
            <option value="OUTBOUND">Outbound</option>
            <option value="INBOUND">Inbound</option>
          </select>

          <select
            className="rounded border border-slate-600 bg-bg px-2 py-1 text-sm text-text-primary"
            value={uboStatus}
            onChange={(e) => setUboStatus(e.target.value as UboStatus | "")}
          >
            <option value="">All UBO statuses</option>
            <option value="FULL">FULL</option>
            <option value="PARTIAL">PARTIAL</option>
            <option value="UNRESOLVED">UNRESOLVED</option>
          </select>

          <input
            className="rounded border border-slate-600 bg-bg px-2 py-1 text-sm text-text-primary"
            placeholder="Country code"
            value={country}
            onChange={(e) => setCountry(e.target.value.toUpperCase())}
          />
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {loading && <div className="p-6 text-text-secondary">Loading queue…</div>}
        {error && (
          <div className="p-6 text-sm" style={{ color: VERDICT_COLORS.MATCH }}>
            Failed to load queue: {error}
          </div>
        )}
        {!loading && !error && items.length === 0 && (
          <div className="p-6 text-text-secondary">No items in queue matching these filters.</div>
        )}
        {!loading && !error && items.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-surface text-xs uppercase text-text-secondary">
              <tr>
                <th className="px-3 py-2">Priority</th>
                <th className="px-3 py-2">Entity</th>
                <th className="px-3 py-2">Country</th>
                <th className="px-3 py-2">Score</th>
                <th className="px-3 py-2">Lists Flagged</th>
                <th className="px-3 py-2">Amount</th>
                <th className="px-3 py-2">Transfer Type</th>
                <th className="px-3 py-2">UBO</th>
                <th className="px-3 py-2">Policy Flags</th>
                <th className="px-3 py-2">SLA</th>
                <th className="px-3 py-2">Assigned</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const verdict = verdictFromTrack(item);
                const borderColor = item.network_escalation_applied ? "#7C3AED" : VERDICT_COLORS[verdict];
                return (
                  <tr
                    key={item.payment_id}
                    onClick={() => navigate(`/case/${item.payment_id}`)}
                    className="cursor-pointer border-b border-slate-700/50 hover:bg-surface/80"
                    style={{ borderLeft: `4px solid ${borderColor}` }}
                  >
                    <td className="px-3 py-2">
                      {item.high_priority ? (
                        <span className="font-semibold" style={{ color: VERDICT_COLORS.MATCH }}>
                          HIGH
                        </span>
                      ) : (
                        <VerdictBadge verdict={verdict} />
                      )}
                    </td>
                    <td className="px-3 py-2 text-text-primary">{item.entity_name}</td>
                    <td className="px-3 py-2 text-text-secondary">{item.country ?? "—"}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono-num">{item.score.toFixed(2)}</span>
                        <span className="relative h-1.5 w-16 overflow-hidden rounded bg-slate-700">
                          <span
                            className="absolute inset-y-0 left-0 rounded"
                            style={{ width: `${item.score * 100}%`, backgroundColor: VERDICT_COLORS[verdict] }}
                          />
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-text-secondary">{item.lists_flagged.join(", ") || "—"}</td>
                    <td className="font-mono-num px-3 py-2 text-text-secondary">
                      {item.amount_usd ? `$${item.amount_usd.toLocaleString()}` : "—"}
                    </td>
                    <td className="px-3 py-2">
                      <TransferTypeBadge type={item.transfer_type} />
                    </td>
                    <td className="px-3 py-2">
                      {item.ubo_resolution_status === "UNRESOLVED" && (
                        <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: "#EA580C" }} />
                      )}
                      <span className="ml-1 text-xs text-text-secondary">{item.ubo_resolution_status}</span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        {item.policy_flags.map((f) => (
                          <PolicyFlagBadge key={f} flag={f} />
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <SlaBadge slaDeadline={item.sla_deadline} />
                    </td>
                    <td className="px-3 py-2 text-text-secondary">{item.assigned_to ?? "Unassigned"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
