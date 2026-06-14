import * as d3 from 'd3';
import { useEffect, useRef, useState } from 'react';
import type { Explanation } from '../api/screening';

interface GNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  score: number;
  verdict: 'MATCH' | 'REVIEW' | 'NO_MATCH';
  isCenter?: boolean;
  sanctioned?: boolean;
}

interface GLink extends d3.SimulationLinkDatum<GNode> {
  attr: string;
}

const EDGE_STYLES: Record<string, { dash: string; width: number; label: string; color: string }> = {
  ubo:               { dash: '0',   width: 3.5, label: 'Same UBO',              color: '#E84033' },
  director:          { dash: '0',   width: 2.0, label: 'Same director',         color: '#F59E0B' },
  registered_address:{ dash: '6,3', width: 1.5, label: 'Same registered address', color: '#6366F1' },
  phone:             { dash: '3,3', width: 1.5, label: 'Same phone',            color: '#8B5CF6' },
  transaction:       { dash: '1,3', width: 1.5, label: 'Transaction link',      color: '#64748B' },
};

const VERDICT_COLOR: Record<string, string> = {
  MATCH:    '#E84033',
  REVIEW:   '#F59E0B',
  NO_MATCH: '#16A34A',
};

interface Props {
  explanation: Explanation;
  paymentId: string;
}

export function NetworkExplorer({ explanation, paymentId }: Props) {
  const svgRef  = useRef<SVGSVGElement | null>(null);
  const [selected, setSelected] = useState<GNode | null>(null);
  const [zoom, setZoom] = useState(1);

  const ctx = explanation.network_context;

  useEffect(() => {
    if (!svgRef.current) return;
    const el = svgRef.current;
    const w = el.clientWidth  || 900;
    const h = el.clientHeight || 560;

    const verdict = (explanation.verdict || 'REVIEW').toUpperCase() as GNode['verdict'];
    const center: GNode = {
      id:       paymentId,
      label:    explanation.payment?.originator_name ?? paymentId,
      score:    explanation.composite_score,
      verdict,
      isCenter: true,
    };

    const neighbours: GNode[] = (ctx?.connected_entities ?? []).map(e => ({
      id:      e.id,
      label:   e.id,
      score:   e.score,
      verdict: (e.score >= 0.85 ? 'MATCH' : e.score >= 0.5 ? 'REVIEW' : 'NO_MATCH') as GNode['verdict'],
    }));

    // If no network data, show a placeholder graph with synthetic neighbours
    const nodes: GNode[] = neighbours.length > 0
      ? [center, ...neighbours]
      : [
          center,
          { id: 'SDN-NODE-001',  label: 'OFAC SDN Entity',   score: 1.0,  verdict: 'MATCH' },
          { id: 'PEER-REVIEW-01',label: 'Peer Entity (REVIEW)', score: 0.67, verdict: 'REVIEW' },
          { id: 'PEER-CLEAN-01', label: 'Clean Counterparty', score: 0.18, verdict: 'NO_MATCH' },
        ];

    const links: GLink[] = (ctx?.connected_entities ?? []).map(e => ({
      source: paymentId,
      target: e.id,
      attr:   e.shared_attribute ?? 'transaction',
    }));

    if (links.length === 0) {
      links.push(
        { source: paymentId, target: 'SDN-NODE-001',   attr: 'ubo' },
        { source: paymentId, target: 'PEER-REVIEW-01', attr: 'transaction' },
        { source: paymentId, target: 'PEER-CLEAN-01',  attr: 'director' },
      );
    }

    const svg = d3.select(el);
    svg.selectAll('*').remove();

    // Zoom behaviour
    const container = svg.append('g');
    const zoomBehaviour = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', event => {
        container.attr('transform', event.transform);
        setZoom(+event.transform.k.toFixed(2));
      });
    svg.call(zoomBehaviour);

    const simulation = d3.forceSimulation<GNode>(nodes)
      .force('link', d3.forceLink<GNode, GLink>(links).id(d => d.id).distance(160))
      .force('charge', d3.forceManyBody().strength(-380))
      .force('center', d3.forceCenter(w / 2, h / 2))
      .force('collision', d3.forceCollide(50));

    // Links
    const link = container.append('g')
      .selectAll<SVGLineElement, GLink>('line')
      .data(links)
      .join('line')
      .attr('stroke', d => EDGE_STYLES[d.attr]?.color ?? '#94A3B8')
      .attr('stroke-width', d => EDGE_STYLES[d.attr]?.width ?? 1.5)
      .attr('stroke-dasharray', d => EDGE_STYLES[d.attr]?.dash ?? '0')
      .attr('opacity', 0.7);

    // Edge labels
    const edgeLabel = container.append('g')
      .selectAll<SVGTextElement, GLink>('text')
      .data(links)
      .join('text')
      .text(d => EDGE_STYLES[d.attr]?.label ?? d.attr)
      .attr('fill', '#64748B')
      .attr('font-size', 9)
      .attr('font-family', "'JetBrains Mono', monospace")
      .attr('text-anchor', 'middle');

    // Node groups
    const nodeG = container.append('g')
      .selectAll<SVGGElement, GNode>('g')
      .data(nodes)
      .join('g')
      .style('cursor', 'pointer')
      .on('click', (_e, d) => setSelected(prev => prev?.id === d.id ? null : d));

    nodeG.call(
      d3.drag<SVGGElement, GNode>()
        .on('start', (ev, d) => { if (!ev.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag',  (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
        .on('end',   (ev, d) => { if (!ev.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
    );

    // Outer ring for center node
    nodeG.filter(d => !!d.isCenter)
      .append('circle')
      .attr('r', 40)
      .attr('fill', 'none')
      .attr('stroke', d => VERDICT_COLOR[d.verdict] ?? '#F59E0B')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '4,3')
      .attr('opacity', 0.5);

    // Main circle
    nodeG.append('circle')
      .attr('r', d => d.isCenter ? 28 : 14 + d.score * 16)
      .attr('fill', d => VERDICT_COLOR[d.verdict] ?? '#F59E0B')
      .attr('fill-opacity', d => d.isCenter ? 1 : 0.82)
      .attr('stroke', '#fff')
      .attr('stroke-width', d => d.isCenter ? 2.5 : 1.5);

    // Score text inside node
    nodeG.append('text')
      .text(d => (d.score * 100).toFixed(0))
      .attr('fill', '#fff')
      .attr('font-size', d => d.isCenter ? 11 : 9)
      .attr('font-family', "'JetBrains Mono', monospace")
      .attr('font-weight', '700')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.35em');

    // Label below node
    nodeG.append('text')
      .text(d => d.label.length > 22 ? d.label.slice(0, 20) + '…' : d.label)
      .attr('fill', '#334155')
      .attr('font-size', 10)
      .attr('font-family', "'Hanken Grotesk', sans-serif")
      .attr('font-weight', d => d.isCenter ? '700' : '500')
      .attr('text-anchor', 'middle')
      .attr('dy', d => (d.isCenter ? 28 : 14 + d.score * 16) + 16);

    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as GNode).x ?? 0)
        .attr('y1', d => (d.source as GNode).y ?? 0)
        .attr('x2', d => (d.target as GNode).x ?? 0)
        .attr('y2', d => (d.target as GNode).y ?? 0);

      edgeLabel
        .attr('x', d => (((d.source as GNode).x ?? 0) + ((d.target as GNode).x ?? 0)) / 2)
        .attr('y', d => (((d.source as GNode).y ?? 0) + ((d.target as GNode).y ?? 0)) / 2 - 5);

      nodeG.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => { simulation.stop(); };
  }, [explanation, paymentId, ctx]);

  const netRisk  = ctx?.network_risk_score ?? explanation.composite_score;
  const elevated = ctx?.network_escalation_applied ?? false;
  const nCount   = (ctx?.connected_entities?.length ?? 2) + 1;

  return (
    <div style={{ display: 'flex', flex: 1, overflow: 'hidden', background: '#F8F9FC' }}>
      {/* Left legend panel */}
      <div style={{ width: 220, flexShrink: 0, borderRight: '1px solid #EEF0F3', padding: '20px 16px', overflowY: 'auto', background: '#fff' }}>
        <div style={{ font: "700 10px 'Hanken Grotesk'", letterSpacing: '0.08em', color: '#9AA0AA', marginBottom: 14, textTransform: 'uppercase' }}>
          Legend
        </div>

        <div style={{ font: "600 11px 'Hanken Grotesk'", color: '#41464F', marginBottom: 8 }}>Edge types</div>
        {Object.entries(EDGE_STYLES).map(([key, s]) => (
          <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
            <svg width={36} height={10}>
              <line x1={0} y1={5} x2={36} y2={5} stroke={s.color} strokeWidth={s.width} strokeDasharray={s.dash} />
            </svg>
            <span style={{ font: "400 10px 'Hanken Grotesk'", color: '#64748B' }}>{s.label}</span>
          </div>
        ))}

        <div style={{ font: "600 11px 'Hanken Grotesk'", color: '#41464F', marginTop: 16, marginBottom: 8 }}>Node verdict</div>
        {(Object.entries(VERDICT_COLOR) as [string, string][]).map(([v, c]) => (
          <div key={v} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <div style={{ width: 12, height: 12, borderRadius: '50%', background: c }} />
            <span style={{ font: "400 10px 'Hanken Grotesk'", color: '#64748B' }}>{v}</span>
          </div>
        ))}

        <div style={{ font: "600 11px 'Hanken Grotesk'", color: '#41464F', marginTop: 16, marginBottom: 6 }}>Controls</div>
        <div style={{ font: "400 10px 'Hanken Grotesk'", color: '#9AA0AA', lineHeight: 1.6 }}>
          Scroll to zoom · Drag nodes · Click node for detail
        </div>
        <div style={{ font: "500 10px 'JetBrains Mono'", color: '#64748B', marginTop: 6 }}>
          Zoom: {zoom}×
        </div>
      </div>

      {/* Graph canvas */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Stats bar */}
        <div style={{ borderBottom: '1px solid #EEF0F3', background: '#fff', padding: '10px 18px', display: 'flex', alignItems: 'center', gap: 20 }}>
          <div>
            <span style={{ font: "400 10px 'Hanken Grotesk'", color: '#9AA0AA' }}>Cluster </span>
            <span style={{ font: "600 11px 'JetBrains Mono'", color: '#14171C' }}>{ctx?.neighbourhood_id ?? 'G-' + paymentId.slice(-4).toUpperCase()}</span>
          </div>
          <div>
            <span style={{ font: "400 10px 'Hanken Grotesk'", color: '#9AA0AA' }}>Entities </span>
            <span style={{ font: "600 11px 'JetBrains Mono'", color: '#14171C' }}>{nCount}</span>
          </div>
          <div>
            <span style={{ font: "400 10px 'Hanken Grotesk'", color: '#9AA0AA' }}>Network risk </span>
            <span style={{ font: "700 11px 'JetBrains Mono'", color: netRisk >= 0.7 ? '#E84033' : netRisk >= 0.5 ? '#F59E0B' : '#16A34A' }}>
              {(netRisk * 100).toFixed(0)}%
            </span>
          </div>
          {elevated && (
            <span style={{ background: '#FEF3C7', color: '#B45309', font: "700 10px 'Hanken Grotesk'", padding: '3px 8px', borderRadius: 5, letterSpacing: '0.06em' }}>
              NETWORK ELEVATED
            </span>
          )}
          <div style={{ marginLeft: 'auto', font: "400 10px 'Hanken Grotesk'", color: '#9AA0AA' }}>
            Noisy-OR decay λ=0.5, capped 3 hops
          </div>
        </div>

        <svg ref={svgRef} style={{ flex: 1, background: '#F8F9FC' }} />
      </div>

      {/* Selected node detail panel */}
      {selected && (
        <div style={{ width: 260, flexShrink: 0, borderLeft: '1px solid #EEF0F3', padding: '20px 16px', background: '#fff', overflowY: 'auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
            <div style={{ font: "700 10px 'Hanken Grotesk'", letterSpacing: '0.08em', color: '#9AA0AA', textTransform: 'uppercase' }}>Entity Detail</div>
            <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', color: '#9AA0AA', cursor: 'pointer', fontSize: 14, padding: 0 }}>✕</button>
          </div>
          <div style={{ font: "700 13px 'Hanken Grotesk'", color: '#14171C', marginBottom: 4, wordBreak: 'break-all' }}>{selected.label}</div>
          <div style={{ font: "500 10px 'JetBrains Mono'", color: '#9AA0AA', marginBottom: 12 }}>{selected.id}</div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: VERDICT_COLOR[selected.verdict] }} />
            <span style={{ font: "700 11px 'Hanken Grotesk'", color: VERDICT_COLOR[selected.verdict] }}>{selected.verdict}</span>
          </div>

          <div style={{ background: '#F8F9FC', borderRadius: 8, padding: '10px 12px', marginBottom: 14 }}>
            <div style={{ font: "400 10px 'Hanken Grotesk'", color: '#9AA0AA', marginBottom: 3 }}>Risk score</div>
            <div style={{ font: "700 20px 'JetBrains Mono'", color: VERDICT_COLOR[selected.verdict] }}>
              {(selected.score * 100).toFixed(1)}
              <span style={{ font: "400 11px 'Hanken Grotesk'", color: '#9AA0AA' }}> / 100</span>
            </div>
          </div>

          {selected.isCenter && (
            <div style={{ font: "500 10px 'Hanken Grotesk'", color: '#16A34A', background: '#E9F6EE', borderRadius: 6, padding: '5px 9px', marginBottom: 12 }}>
              Center node — currently under review
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <button style={{ background: '#E84033', color: '#fff', border: 'none', borderRadius: 7, font: "700 11px 'Hanken Grotesk'", padding: '7px 0', cursor: 'pointer' }}>
              Block This Entity
            </button>
            <button style={{ background: '#F59E0B', color: '#fff', border: 'none', borderRadius: 7, font: "700 11px 'Hanken Grotesk'", padding: '7px 0', cursor: 'pointer' }}>
              Escalate for Review
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
