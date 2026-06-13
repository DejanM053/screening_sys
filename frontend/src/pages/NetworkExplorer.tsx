import * as d3 from "d3";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchExplanation } from "../api/client";
import { ClusterBadge } from "../components/Badges";
import type { ExplanationResponse } from "../types";
import { CLUSTER_COLOR, UBO_COLOR, VERDICT_COLORS } from "../types";

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  score: number;
  verdict: "MATCH" | "REVIEW" | "NO_MATCH";
  uboUnresolved?: boolean;
  sanctioned?: boolean;
  isCenter?: boolean;
}

interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
  sharedAttribute: string;
}

const EDGE_STYLES: Record<string, { dash: string; width: number; label: string }> = {
  ubo: { dash: "0", width: 4, label: "Same UBO" },
  director: { dash: "0", width: 2.5, label: "Same director" },
  registered_address: { dash: "0", width: 1.5, label: "Same registered address" },
  phone: { dash: "6,4", width: 1.5, label: "Same phone" },
  transaction: { dash: "1,3", width: 1.5, label: "Transaction link" },
};

export function NetworkExplorer() {
  const { paymentId } = useParams<{ paymentId: string }>();
  const [explanation, setExplanation] = useState<ExplanationResponse | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    if (!paymentId) return;
    fetchExplanation(paymentId).then(setExplanation).catch(() => setExplanation(null));
  }, [paymentId]);

  useEffect(() => {
    if (!explanation?.network_context || !svgRef.current) return;

    const width = svgRef.current.clientWidth || 800;
    const height = svgRef.current.clientHeight || 600;

    const centerId = explanation.payment_id;
    const nodes: GraphNode[] = [
      { id: centerId, score: explanation.composite_score, verdict: explanation.verdict, isCenter: true },
      ...explanation.network_context.connected_entities.map((e) => ({
        id: e.id,
        score: e.score,
        verdict: (e.score >= 0.85 ? "MATCH" : e.score >= 0.5 ? "REVIEW" : "NO_MATCH") as GraphNode["verdict"],
      })),
    ];

    const links: GraphLink[] = explanation.network_context.connected_entities.map((e) => ({
      source: centerId,
      target: e.id,
      sharedAttribute: e.shared_attribute ?? "transaction",
    }));

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink<GraphNode, GraphLink>(links)
          .id((d) => d.id)
          .distance(140)
      )
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2));

    const link = svg
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", "#475569")
      .attr("stroke-width", (d) => EDGE_STYLES[d.sharedAttribute]?.width ?? 1.5)
      .attr("stroke-dasharray", (d) => EDGE_STYLES[d.sharedAttribute]?.dash ?? "0");

    const node = svg
      .append("g")
      .selectAll<SVGCircleElement, GraphNode>("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d) => 12 + d.score * 24)
      .attr("fill", (d) => VERDICT_COLORS[d.verdict])
      .attr("stroke", (d) => (d.isCenter ? "#FFFFFF" : "transparent"))
      .attr("stroke-width", 3)
      .style("cursor", "pointer")
      .on("click", (_event, d) => setSelected(d));

    node.call(
      d3
        .drag<SVGCircleElement, GraphNode>()
        .on("start", (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
    );

    const label = svg
      .append("g")
      .selectAll("text")
      .data(nodes)
      .join("text")
      .text((d) => `${d.id} (${d.score.toFixed(2)})`)
      .attr("fill", "#F1F5F9")
      .attr("font-size", 11)
      .attr("text-anchor", "middle")
      .attr("dy", -18);

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as GraphNode).x ?? 0)
        .attr("y1", (d) => (d.source as GraphNode).y ?? 0)
        .attr("x2", (d) => (d.target as GraphNode).x ?? 0)
        .attr("y2", (d) => (d.target as GraphNode).y ?? 0);

      node.attr("cx", (d) => d.x ?? 0).attr("cy", (d) => d.y ?? 0);
      label.attr("x", (d) => d.x ?? 0).attr("y", (d) => d.y ?? 0);
    });

    return () => {
      simulation.stop();
    };
  }, [explanation]);

  if (!explanation) {
    return <div className="flex flex-1 items-center justify-center text-text-secondary">Loading network…</div>;
  }

  const ctx = explanation.network_context;

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="w-64 flex-shrink-0 border-r border-slate-700 p-4">
        <h2 className="mb-3 text-sm font-bold uppercase text-text-secondary">Legend</h2>
        {Object.entries(EDGE_STYLES).map(([key, style]) => (
          <div key={key} className="mb-2 flex items-center gap-2 text-xs text-text-secondary">
            <svg width="32" height="8">
              <line x1="0" y1="4" x2="32" y2="4" stroke="#475569" strokeWidth={style.width} strokeDasharray={style.dash} />
            </svg>
            {style.label}
          </div>
        ))}
        <div className="mt-4 space-y-1 text-xs text-text-secondary">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full" style={{ backgroundColor: VERDICT_COLORS.MATCH }} /> MATCH
          </div>
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full" style={{ backgroundColor: VERDICT_COLORS.REVIEW }} /> REVIEW
          </div>
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full" style={{ backgroundColor: VERDICT_COLORS.NO_MATCH }} /> NO_MATCH
          </div>
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full border-2" style={{ borderColor: UBO_COLOR }} /> UBO unresolved
          </div>
        </div>
      </div>

      <div className="flex flex-1 flex-col">
        <div className="flex items-center gap-4 border-b border-slate-700 bg-surface px-4 py-3">
          {ctx ? (
            <>
              <span className="text-sm text-text-secondary">
                Cluster <span className="text-text-primary">{ctx.neighbourhood_id}</span>
              </span>
              <span className="text-sm text-text-secondary">
                Entities: <span className="font-mono-num text-text-primary">{ctx.neighbour_count + 1}</span>
              </span>
              <span className="text-sm text-text-secondary">
                Network risk: <span className="font-mono-num text-text-primary">{ctx.network_risk_score.toFixed(2)}</span>
              </span>
              {ctx.network_escalation_applied && <ClusterBadge label="REVIEW ELEVATED" />}
            </>
          ) : (
            <span className="text-sm text-text-secondary">No network cluster context for this payment.</span>
          )}
        </div>
        <svg ref={svgRef} className="flex-1" style={{ backgroundColor: "#0F172A" }} />
      </div>

      {selected && (
        <div className="w-80 flex-shrink-0 border-l border-slate-700 p-4">
          <h2 className="mb-2 text-sm font-bold uppercase text-text-secondary">Entity Detail</h2>
          <div className="font-mono-num text-lg text-text-primary">{selected.id}</div>
          <div className="mt-1 text-sm" style={{ color: VERDICT_COLORS[selected.verdict] }}>
            {selected.verdict}
          </div>
          <div className="mt-2 font-mono-num text-sm text-text-secondary">Score: {selected.score.toFixed(2)}</div>
          <div className="mt-4 flex flex-col gap-2">
            <button className="rounded px-3 py-2 text-sm font-semibold text-white" style={{ backgroundColor: VERDICT_COLORS.MATCH }}>
              Block This Entity
            </button>
            <button className="rounded px-3 py-2 text-sm font-semibold text-white" style={{ backgroundColor: CLUSTER_COLOR }}>
              Escalate This Entity
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
