import { Case, composite } from '../data/cases';
import { vMeta, tierMeta, flagMeta, slaMeta } from '../utils/design';
import { QueueItem } from '../api/screening';

interface Props {
  cases: Case[];
  decidedCases?: Case[];
  decidedItems?: QueueItem[];
  tFilter: string; setTFilter: (v: string) => void;
  vFilter: string; setVFilter: (v: string) => void;
  onOpen: (id: string) => void;
}

export function QueueDashboard({ cases, decidedCases = [], decidedItems = [], tFilter, setTFilter, vFilter, setVFilter, onOpen }: Props) {
  const rows = cases.map(c => {
    const vm = vMeta(c.verdict), tm = tierMeta(c.tier), sm = slaMeta(c.slaMins);
    const comp = composite(c);
    const isMatch = c.verdict === 'MATCH';
    return {
      ...c,
      slaColor: sm.color, slaHalo: sm.halo, slaLabel: sm.label,
      scoreDisplay: comp != null ? comp.toFixed(2) : '—',
      scorePct: Math.round((comp || 0) * 100),
      scoreInk: isMatch ? vm.color : '#14171C',
      verdictColor: vm.color, verdictBg: vm.bg, verdictBorder: vm.border,
      tierFg: tm.fg, tierBg: tm.bg,
      flagsMeta: (c.flags || []).map(l => { const fm = flagMeta(l); return { label: l, ...fm }; }),
    };
  });

  const filtered = rows.filter(r => {
    const tOk = tFilter === 'all' || r.transfer === tFilter;
    const vOk = vFilter === 'all' || r.verdict === vFilter;
    return tOk && vOk;
  });

  const countV = (v: string) => cases.filter(c => c.verdict === v).length;
  const urgent = cases.filter(c => c.slaMins < 15).length;
  const decidedBlocked = decidedItems.filter(d => d.decision === 'BLOCK').length;
  const decidedCleared = decidedItems.filter(d => d.decision === 'CLEAR').length;
  const stats = [
    { value: countV('REVIEW'), color: '#D97706', label: 'Pending review' },
    { value: countV('MATCH'),  color: '#DC2626', label: 'System blocked' },
    { value: decidedCleared, color: '#16A34A', label: 'Cleared' },
    { value: decidedBlocked, color: '#DC2626', label: 'Analyst blocked' },
    { value: urgent, color: urgent > 0 ? '#DC2626' : '#6B7280', label: 'SLA < 15m' },
  ];

  const mkTF = (key: string, label: string) => {
    const on = tFilter === key;
    return { label, onClick: () => setTFilter(key), bg: on ? '#14171C' : '#fff', fg: on ? '#fff' : '#41464F', border: on ? '#14171C' : '#E1E4E9' };
  };
  const mkVF = (key: string, label: string, dot: string) => {
    const on = vFilter === key;
    return { label, dot, onClick: () => setVFilter(key), bg: on ? '#14171C' : '#fff', fg: on ? '#fff' : '#41464F', border: on ? '#14171C' : '#E1E4E9' };
  };
  const transferFilters = [mkTF('all', 'All'), mkTF('Internal', 'Internal'), mkTF('Outbound', 'Outbound'), mkTF('Inbound', 'Inbound')];
  const verdictFilters = [mkVF('all', 'All', '#9AA0AA'), mkVF('MATCH', 'MATCH', '#DC2626'), mkVF('REVIEW', 'REVIEW', '#D97706'), mkVF('NO_MATCH', 'NO_MATCH', '#16A34A')];
  const batchClearable = cases.filter(c => c.verdict === 'NO_MATCH' && c.transfer === 'Internal' && (composite(c) || 0) < 0.25).length;

  return (
    <main className="gs-scroll" style={{ flex: '1 1 auto', overflow: 'auto', padding: '4px 16px 24px' }}>
      <div style={{ maxWidth: 1320, margin: '0 auto' }}>

        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', margin: '6px 0 14px' }}>
          <div>
            <h1 style={{ margin: 0, font: "800 21px 'Hanken Grotesk'", letterSpacing: '-0.02em', color: '#14171C' }}>Review Queue</h1>
            <p style={{ margin: '5px 0 0', font: "400 12.5px 'Hanken Grotesk'", color: '#757B86' }}>Priority-sorted by Track B risk · MATCH items are blocked, shown for sign-off · association routes to REVIEW, lists to MATCH</p>
          </div>
          <div style={{ display: 'flex', gap: 9 }}>
            {stats.map(s => (
              <div key={s.label} style={{ background: '#fff', border: '1px solid #E1E4E9', borderRadius: 11, padding: '10px 15px', minWidth: 80, boxShadow: '0 1px 2px rgba(20,23,28,0.03)' }}>
                <div style={{ font: "700 22px 'JetBrains Mono'", color: s.color, lineHeight: 1 }}>{s.value}</div>
                <div style={{ font: "600 10px/1.3 'Hanken Grotesk'", color: '#757B86', textTransform: 'uppercase', letterSpacing: '.06em', marginTop: 6 }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, background: '#fff', border: '1px solid #E1E4E9', borderRadius: 11, padding: '9px 13px', marginBottom: 12, flexWrap: 'wrap', boxShadow: '0 1px 2px rgba(20,23,28,0.03)' }}>
          <span style={{ font: "700 10px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.08em' }}>Transfer</span>
          <div style={{ display: 'flex', gap: 4 }}>
            {transferFilters.map(t => (
              <button key={t.label} onClick={t.onClick} style={{ border: `1px solid ${t.border}`, background: t.bg, color: t.fg, font: "600 11.5px 'Hanken Grotesk'", padding: '6px 12px', borderRadius: 8, transition: 'all .1s' }}>{t.label}</button>
            ))}
          </div>
          <div style={{ width: 1, height: 22, background: '#E1E4E9' }} />
          <span style={{ font: "700 10px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.08em' }}>Verdict</span>
          <div style={{ display: 'flex', gap: 4 }}>
            {verdictFilters.map(v => (
              <button key={v.label} onClick={v.onClick} style={{ border: `1px solid ${v.border}`, background: v.bg, color: v.fg, font: "600 11.5px 'Hanken Grotesk'", padding: '6px 12px', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 6, transition: 'all .1s' }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: v.dot }} />
                {v.label}
              </button>
            ))}
          </div>
          <span style={{ marginLeft: 'auto', font: "500 11px 'JetBrains Mono'", color: '#9AA0AA' }}>{filtered.length} / {rows.length} shown</span>
        </div>

        {/* table */}
        <div style={{ background: '#fff', border: '1px solid #E1E4E9', borderRadius: 13, overflow: 'hidden', boxShadow: '0 1px 3px rgba(20,23,28,0.04)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '88px 1.7fr 138px 118px 1fr 130px 146px', padding: '0 16px', height: 40, alignItems: 'center', borderBottom: '1px solid #E1E4E9', background: '#FAFBFC', font: "700 10px 'Hanken Grotesk'", color: '#8A909B', textTransform: 'uppercase', letterSpacing: '.07em' }}>
            <div>SLA</div><div>Entity</div><div>Risk score</div><div>Verdict</div><div>Lists / track</div><div>Country</div><div>Flags</div>
          </div>
          {filtered.map(row => (
            <div key={row.id} className="gs-row" onClick={() => onOpen(row.id)} style={{ display: 'grid', gridTemplateColumns: '88px 1.7fr 138px 118px 1fr 130px 146px', padding: '13px 16px', alignItems: 'center', borderBottom: '1px solid #F0F2F4', cursor: 'pointer', transition: 'background .08s' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: row.slaColor, boxShadow: `0 0 0 3px ${row.slaHalo}` }} />
                <span style={{ font: "600 12px 'JetBrains Mono'", color: row.slaColor }}>{row.slaLabel}</span>
              </div>
              <div style={{ paddingRight: 14 }}>
                <div style={{ font: "600 13.5px 'Hanken Grotesk'", color: '#14171C' }}>{row.entity}</div>
                <div style={{ font: "500 11px 'JetBrains Mono'", color: '#9AA0AA', marginTop: 2 }}>{row.id} · {row.transfer}</div>
              </div>
              <div style={{ paddingRight: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ font: "600 13px 'JetBrains Mono'", color: row.scoreInk, width: 32 }}>{row.scoreDisplay}</div>
                  <div style={{ flex: 1, height: 5, background: '#EEF0F3', borderRadius: 3, position: 'relative', overflow: 'hidden' }}>
                    <div style={{ position: 'absolute', left: '50%', top: -1, width: 1, height: 7, background: '#B4BAC2', zIndex: 1 }} />
                    <div style={{ height: '100%', width: `${row.scorePct}%`, background: row.verdictColor, borderRadius: 3 }} />
                  </div>
                </div>
              </div>
              <div>
                <span style={{ display: 'inline-flex', alignItems: 'center', background: row.verdictBg, color: row.verdictColor, font: "700 10px 'Hanken Grotesk'", letterSpacing: '.04em', padding: '4px 9px', borderRadius: 6, border: `1px solid ${row.verdictBorder}` }}>{row.verdict}</span>
              </div>
              <div style={{ paddingRight: 14 }}>
                {row.lists !== '—' && <div style={{ font: "500 11px 'JetBrains Mono'", color: '#41464F', marginBottom: 2 }}>{row.lists}</div>}
                <div style={{ font: "500 10.5px 'JetBrains Mono'", color: '#9AA0AA' }}>{row.track}</div>
              </div>
              <div>
                <div style={{ font: "600 12px 'Hanken Grotesk'", color: '#14171C' }}>{row.country}</div>
                <div style={{ display: 'inline-block', font: "600 9px 'JetBrains Mono'", color: row.tierFg, background: row.tierBg, borderRadius: 4, padding: '2px 6px', marginTop: 3, letterSpacing: '.04em' }}>{row.tier}</div>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {row.flagsMeta.map(fl => (
                  <span key={fl.label} style={{ font: "600 9px 'JetBrains Mono'", color: fl.color, background: fl.bg, border: `1px solid ${fl.border}`, borderRadius: 5, padding: '2px 6px' }}>{fl.label}</span>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 13 }}>
          <button style={{ display: 'flex', alignItems: 'center', gap: 9, background: '#fff', border: '1px solid #E1E4E9', borderRadius: 9, font: "600 12px 'Hanken Grotesk'", color: '#41464F', padding: '9px 14px', boxShadow: '0 1px 2px rgba(20,23,28,0.03)' }}>
            <span style={{ width: 15, height: 15, border: '1.5px solid #16A34A', borderRadius: 4, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: '#16A34A', fontSize: 10 }}>✓</span>
            Batch-clear {batchClearable} low-confidence NO_MATCH · internal, score &lt; 0.25
          </button>
          <span style={{ font: "400 11px 'Hanken Grotesk'", color: '#9AA0AA' }}>Every decision writes a who / what / when / why audit record · 5-year retention</span>
        </div>

        {/* DECIDED / HISTORY SECTION — always visible */}
        <div style={{ marginTop: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <h2 style={{ margin: 0, font: "700 15px 'Hanken Grotesk'", color: '#41464F', letterSpacing: '-0.01em' }}>Recent Decisions</h2>
            <span style={{ font: "600 10px 'JetBrains Mono'", color: '#9AA0AA', border: '1px solid #E1E4E9', borderRadius: 5, padding: '3px 7px' }}>{decidedCases.length} reviewed</span>
          </div>
          {decidedCases.length === 0 ? (
            <div style={{ background: '#fff', border: '1px solid #E1E4E9', borderRadius: 13, padding: '22px 20px', textAlign: 'center', boxShadow: '0 1px 3px rgba(20,23,28,0.04)' }}>
              <div style={{ font: "600 13px 'Hanken Grotesk'", color: '#B4BAC2' }}>No decisions yet</div>
              <div style={{ font: "400 11.5px 'Hanken Grotesk'", color: '#C9CDD3', marginTop: 5 }}>Open a case and use CLEAR / BLOCK / ESCALATE to record a decision — it will appear here.</div>
            </div>
          ) : (
            <div style={{ background: '#fff', border: '1px solid #E1E4E9', borderRadius: 13, overflow: 'hidden', boxShadow: '0 1px 3px rgba(20,23,28,0.04)' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1.7fr 118px 130px 1fr 160px', padding: '0 16px', height: 38, alignItems: 'center', borderBottom: '1px solid #E1E4E9', background: '#FAFBFC', font: "700 10px 'Hanken Grotesk'", color: '#8A909B', textTransform: 'uppercase', letterSpacing: '.07em' }}>
                <div>Entity</div><div>Verdict</div><div>Country</div><div>Decision</div><div>Decided</div>
              </div>
              {decidedCases.map((c, i) => {
                const di = decidedItems[i];
                const dec = di?.decision ?? '';
                const decAt = di?.decided_at ? new Date(di.decided_at).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—';
                const vm = vMeta(c.verdict);
                const decColor = dec === 'CLEAR' ? '#16A34A' : dec === 'BLOCK' ? '#DC2626' : dec === 'ESCALATE' ? '#D97706' : '#6B7280';
                const decBg    = dec === 'CLEAR' ? '#F0FDF4' : dec === 'BLOCK' ? '#FEF2F2' : dec === 'ESCALATE' ? '#FFFBEB' : '#F9FAFB';
                const decBord  = dec === 'CLEAR' ? '#BBF7D0' : dec === 'BLOCK' ? '#FECACA' : dec === 'ESCALATE' ? '#FDE68A' : '#E1E4E9';
                return (
                  <div key={c.id} className="gs-row" onClick={() => onOpen(c.id)} style={{ display: 'grid', gridTemplateColumns: '1.7fr 118px 130px 1fr 160px', padding: '11px 16px', alignItems: 'center', borderBottom: '1px solid #F0F2F4', cursor: 'pointer', transition: 'background .08s', opacity: 0.85 }}>
                    <div style={{ paddingRight: 14 }}>
                      <div style={{ font: "600 13px 'Hanken Grotesk'", color: '#41464F' }}>{c.entity}</div>
                      <div style={{ font: "500 10.5px 'JetBrains Mono'", color: '#9AA0AA', marginTop: 2 }}>{c.id}</div>
                    </div>
                    <div>
                      <span style={{ display: 'inline-flex', alignItems: 'center', background: vm.bg, color: vm.color, font: "700 10px 'Hanken Grotesk'", letterSpacing: '.04em', padding: '3px 8px', borderRadius: 6, border: `1px solid ${vm.border}` }}>{c.verdict}</span>
                    </div>
                    <div style={{ font: "600 12px 'Hanken Grotesk'", color: '#41464F' }}>{c.country}</div>
                    <div>
                      {dec ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', background: decBg, color: decColor, font: "700 10px 'Hanken Grotesk'", letterSpacing: '.04em', padding: '3px 8px', borderRadius: 6, border: `1px solid ${decBord}` }}>{dec}</span>
                      ) : (
                        <span style={{ font: "500 11px 'JetBrains Mono'", color: '#9AA0AA' }}>—</span>
                      )}
                    </div>
                    <div style={{ font: "500 11px 'JetBrains Mono'", color: '#9AA0AA' }}>{decAt}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </div>
    </main>
  );
}
