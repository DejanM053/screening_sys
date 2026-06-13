import { useState } from "react";
import type { ExplanationResponse, ScoreNode } from "../types";
import { INFO_COLOR, VERDICT_COLORS } from "../types";
import { UboBadge, VerdictBadge } from "./Badges";

const FACTOR_IDS = [
  "identity_match",
  "behavioral_anomaly",
  "network_exposure",
  "entity_risk_profile",
  "doc_integrity",
  "historical_flag_rate",
  "ml_delta",
];

function isPolicyFlag(node: ScoreNode): boolean {
  return node.id.startsWith("policy_flag:");
}

function WaterfallRow({ node }: { node: ScoreNode }) {
  const [expanded, setExpanded] = useState(false);
  const pct = Math.max(0, Math.min(1, node.score ?? 0));
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div className="border-b border-slate-700/50 last:border-b-0">
      <button
        type="button"
        onClick={() => hasChildren && setExpanded((e) => !e)}
        className={`flex w-full items-center gap-3 px-2 py-2 text-left ${hasChildren ? "cursor-pointer hover:bg-surface/60" : "cursor-default"}`}
      >
        <span className="w-44 flex-shrink-0 truncate text-sm text-text-primary">{node.label}</span>
        <span className="relative h-2 flex-1 overflow-hidden rounded bg-slate-700">
          <span
            className="absolute inset-y-0 left-0 rounded bg-accent"
            style={{ width: `${pct * 100}%` }}
          />
        </span>
        <span className="font-mono-num w-24 flex-shrink-0 text-right text-sm text-text-secondary">
          {node.score === null ? "—" : `+${node.weighted_contribution.toFixed(3)}`}
        </span>
        <span className="font-mono-num w-28 flex-shrink-0 text-right text-xs text-text-secondary">
          {node.score === null ? "n/a" : `${(node.score * 100).toFixed(0)}% × ${node.weight}`}
        </span>
        {hasChildren && <span className="text-text-secondary">{expanded ? "▾" : "▸"}</span>}
      </button>
      {expanded && hasChildren && (
        <div className="ml-6 border-l border-slate-700 pl-3 pb-2">
          {node.children.map((child) => (
            <div key={child.id} className="py-1 text-xs text-text-secondary">
              <span className="text-text-primary">{child.label}</span>
              {child.score !== null && (
                <span className="font-mono-num ml-2">{(child.score * 100).toFixed(0)}%</span>
              )}
              {child.detail && <div className="mt-0.5 text-text-secondary">{child.detail}</div>}
            </div>
          ))}
        </div>
      )}
      {!expanded && node.detail && (
        <div className="px-2 pb-2 text-xs text-text-secondary">{node.detail}</div>
      )}
    </div>
  );
}

export function ScoreExplanationCard({
  explanation,
  size = "full",
}: {
  explanation: ExplanationResponse;
  size?: "full" | "compact" | "mobile";
}) {
  const { tree, verdict, composite_score, track, network_context, llm_explanation } = explanation;
  const factorNodes = tree.children.filter((c) => FACTOR_IDS.includes(c.id));
  const policyFlags = tree.children.filter(isPolicyFlag);
  const uboNode = tree.children.find((c) => c.id === "entity_risk_profile");
  const uboStatus = uboNode?.children?.find((c) => c.id === "ubo_resolution");
  const verdictColor = VERDICT_COLORS[verdict];

  if (size === "compact") {
    const top = [...factorNodes]
      .filter((f) => f.score !== null)
      .sort((a, b) => b.weighted_contribution - a.weighted_contribution)
      .slice(0, 2);
    return (
      <div className="flex items-center gap-2">
        <VerdictBadge verdict={verdict} />
        <span className="font-mono-num text-sm" style={{ color: verdictColor }}>
          {composite_score.toFixed(2)}
        </span>
        {top.map((f) => (
          <span key={f.id} className="rounded bg-surface px-1.5 py-0.5 text-xs text-text-secondary">
            {f.label}
          </span>
        ))}
        {uboStatus?.metadata?.ubo_resolution_status === "UNRESOLVED" && (
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: "#EA580C" }} title="UBO unresolved" />
        )}
        {policyFlags.length > 0 && (
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: INFO_COLOR }} title="Policy flag active" />
        )}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-700 bg-surface p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-mono-num text-3xl font-bold" style={{ color: verdictColor }}>
            {composite_score.toFixed(2)}
          </div>
          <div className="mt-1 text-xs text-text-secondary">
            Track B: R &lt; 0.50 = NO_MATCH | R ≥ 0.50 = REVIEW (high-priority above 0.85) — risk score never
            produces a block
          </div>
          <div className="mt-1 text-xs text-text-secondary">Track: {track}</div>
        </div>
        <VerdictBadge verdict={verdict} />
      </div>

      <div className="mt-4 rounded border border-slate-700">
        {factorNodes.map((node) => (
          <WaterfallRow key={node.id} node={node} />
        ))}
        <div className="flex items-center gap-3 px-2 py-2 font-semibold">
          <span className="w-44 flex-shrink-0 text-sm text-text-primary">TOTAL</span>
          <span className="flex-1" />
          <span className="font-mono-num w-24 flex-shrink-0 text-right text-sm" style={{ color: verdictColor }}>
            {composite_score.toFixed(3)}
          </span>
          <span className="w-28" />
        </div>
      </div>

      {policyFlags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {policyFlags.map((flag) => (
            <span
              key={flag.id}
              title={flag.detail}
              className="rounded border px-2 py-1 text-xs"
              style={{ color: INFO_COLOR, borderColor: INFO_COLOR, backgroundColor: `${INFO_COLOR}1A` }}
            >
              ℹ {flag.label}
            </span>
          ))}
        </div>
      )}

      {uboStatus && (
        <div className="mt-3 rounded border border-slate-700 p-3">
          <div className="mb-1 flex items-center gap-2">
            <span className="text-sm font-semibold text-text-primary">UBO Resolution</span>
            <UboBadge status={uboStatus.metadata?.ubo_resolution_status as any} />
          </div>
          <div className="text-xs text-text-secondary">{uboStatus.detail}</div>
          {Boolean(uboStatus.metadata?.review_gate_triggered) && (
            <div className="mt-1 text-xs" style={{ color: "#EA580C" }}>
              Review gate triggered — UBO chain unresolved
            </div>
          )}
        </div>
      )}

      {network_context && (
        <div className="mt-3 rounded border border-slate-700 p-3">
          <div className="mb-1 text-sm font-semibold text-text-primary">Network cluster context</div>
          <div className="font-mono-num text-xs text-text-secondary">
            Neighbourhood {network_context.neighbourhood_id} — {network_context.neighbour_count} neighbours —
            network risk {network_context.network_risk_score.toFixed(2)}
          </div>
          {network_context.network_escalation_applied && (
            <div className="mt-1 text-xs" style={{ color: "#7C3AED" }}>
              {network_context.escalation_reason}
            </div>
          )}
        </div>
      )}

      {llm_explanation && (
        <details className="mt-3 rounded border border-slate-700 p-3">
          <summary className="cursor-pointer text-sm font-semibold text-text-primary">LLM Explanation</summary>
          <p className="mt-2 whitespace-pre-wrap text-xs text-text-secondary">{llm_explanation}</p>
        </details>
      )}
    </div>
  );
}
