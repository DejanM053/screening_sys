import { Case, composite } from '../data/cases';
import { vMeta, flagMeta, uboMeta, slaMeta, tint } from '../utils/design';

interface Props {
  cases: Case[];
  activeId: string;
  drafts: Record<string, string>;
  setDraft: (id: string, v: string) => void;
  decisions: Record<string, { action: string; ts: string }>;
  setDecision: (id: string, action: string) => void;
  onBack: () => void;
  onChallenge?: () => void;
  onOpenNetwork?: () => void;
}

export function CaseDetail({ cases, activeId, drafts, setDraft, decisions, setDecision, onBack, onChallenge, onOpenNetwork }: Props) {
  const ac = cases.find(c => c.id === activeId) || cases[0];
  const avm = vMeta(ac.verdict), asm = slaMeta(ac.slaMins);
  const acomp = composite(ac);
  const um = uboMeta(ac.profile.uboStatus), km = uboMeta(ac.profile.kybStatus);
  const sUbo = uboMeta(ac.pay.senderUbo), rUbo = uboMeta(ac.pay.receiverUbo);
  const dec = decisions[ac.id];
  const decMeta = dec ? vMeta(dec.action === 'BLOCK' ? 'MATCH' : (dec.action === 'CLEAR' ? 'NO_MATCH' : 'REVIEW')) : null;

  const factors = (ac.factors || []).map(f => ({
    ...f,
    scoreStr: f.score.toFixed(2), scoreW: Math.round(f.score * 100),
    weightStr: '×' + f.weight.toFixed(2),
    contribStr: (f.score * f.weight).toFixed(3),
    contribPct: f.score * f.weight * 100,
    tintColor: tint(f.score),
    sub: (f.sub || []).map(s => ({ ...s, sStr: s.s.toFixed(2), tintColor: tint(s.s) })),
  }));

  const net = ac.network;
  const netNoisy = net?.type === 'noisyor';
  const netOwnership = net?.type === 'ownership';
  const netCluster = net?.type === 'cluster';

  const noisyNodes = net?.nodes ? [...net.nodes].reverse().map((n, i) => {
    const col = n.isSdn ? '#DC2626' : (n.hop === 0 ? avm.color : '#D97706');
    const bg = n.isSdn ? '#FCEBEB' : (n.hop === 0 ? avm.bg : '#FBF1E2');
    const glow = n.isSdn ? 'rgba(220,38,38,0.3)' : 'rgba(217,119,6,0.22)';
    const origLen = net.nodes!.length;
    return { ...n, col, bg, glow, taintStr: 'p ' + n.taint.toFixed(1), contribStr: n.contrib.toFixed(2), marginalStr: n.marginal.toFixed(3), edgeDecay: i === 0 ? 'λ²=0.25' : 'λ¹=0.50', hasConnector: i < origLen - 1 };
  }) : [];

  const ownerChain = (net?.chain || []).map((c, i) => ({
    ...c, hasPct: !!c.pct, hasArrow: i < (net!.chain!.length - 1),
    bg: c.sdn ? '#FCEBEB' : '#F7F8FA', border: c.sdn ? '#F3C9C9' : '#EEF0F3',
    ink: c.sdn ? '#DC2626' : '#14171C', sub2: c.sdn ? '#DC2626' : '#9AA0AA',
  }));

  const clusterNodes = (net?.cluster || []).map(c => ({
    ...c, bg: c.subject ? '#FBF1E2' : '#F7F8FA', border: c.subject ? '#EFD7AE' : '#EEF0F3', dot: c.subject ? '#D97706' : '#7C3AED',
  }));

  const adverse = (ac.profile.adverse || []).map(a => ({ ...a, relStr: a.rel.toFixed(2), tintColor: tint(a.rel) }));
  const histFraction = ac.profile.histRate === '—' ? '—' : `(${ac.profile.histHits}+1) / (${ac.profile.histScreen}+10) = ${ac.profile.histRate}`;
  const auditValue = drafts[ac.id] != null ? drafts[ac.id] : ac.audit;

  const mkAction = (label: string, kind: string) => {
    let bg: string, fg: string, border: string;
    if (kind === 'clear')   { bg = '#16A34A'; fg = '#fff'; border = '#16A34A'; }
    else if (kind === 'block')   { bg = '#DC2626'; fg = '#fff'; border = '#DC2626'; }
    else if (kind === 'primary') { bg = '#14171C'; fg = '#fff'; border = '#14171C'; }
    else { bg = '#fff'; fg = '#41464F'; border = '#E1E4E9'; }
    return { label, onClick: () => setDecision(ac.id, label), bg, fg, border };
  };
  const actionButtons = [mkAction('CLEAR', 'clear'), mkAction('BLOCK', 'block'), mkAction('ESCALATE', 'primary'), mkAction('REQUEST INFO', 'ghost'), mkAction('DEFER', 'ghost')];

  const profileRows = [
    { k: 'Registration', v: ac.profile.regNo },
    { k: 'Incorporated', v: ac.profile.incorporated },
    { k: 'Jurisdiction', v: ac.profile.jurisdiction },
    { k: 'Structure', v: ac.profile.structure },
  ];

  return (
    <main className="gs-scroll" style={{ flex: '1 1 auto', overflow: 'auto' }}>

      {/* sticky action bar */}
      <div style={{ position: 'sticky', top: 0, zIndex: 8, background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(8px)', borderBottom: '1px solid #DDE0E5', padding: '11px 18px', display: 'flex', alignItems: 'center', gap: 15 }}>
        <button onClick={onBack} style={{ background: 'none', border: 'none', font: "600 12px 'Hanken Grotesk'", color: '#757B86', display: 'flex', alignItems: 'center', gap: 6, padding: 0, cursor: 'pointer' }}>← Queue</button>
        <div style={{ width: 1, height: 28, background: '#E1E4E9' }} />
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
            <span style={{ font: "800 17px 'Hanken Grotesk'", letterSpacing: '-0.01em', color: '#14171C' }}>{ac.entity}</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', background: avm.bg, color: avm.color, font: "700 11px 'Hanken Grotesk'", letterSpacing: '.04em', padding: '4px 10px', borderRadius: 7, border: `1px solid ${avm.border}` }}>{ac.verdict}</span>
            {(ac.flags || []).map(l => { const fm = flagMeta(l); return <span key={l} style={{ font: "600 10px 'JetBrains Mono'", color: fm.color, background: fm.bg, border: `1px solid ${fm.border}`, borderRadius: 5, padding: '3px 7px' }}>{l}</span>; })}
          </div>
          <div style={{ font: "500 11px 'JetBrains Mono'", color: '#9AA0AA', marginTop: 3 }}>{ac.id} · {ac.entityType} · {ac.trackLong}</div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ font: "600 9px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.07em' }}>SLA left</div>
            <div style={{ font: "600 14px 'JetBrains Mono'", color: asm.color }}>{asm.label}</div>
          </div>
          <div style={{ width: 1, height: 30, background: '#E1E4E9' }} />
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            {dec ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: decMeta?.bg ?? '#F3F5F7', color: decMeta?.color ?? '#41464F', border: `1px solid ${decMeta?.border ?? '#E1E4E9'}`, borderRadius: 8, font: "700 11px 'Hanken Grotesk'", padding: '5px 10px', letterSpacing: '.01em' }}>
                Decision recorded: {dec.action}
              </span>
            ) : (
              actionButtons.map(a => (
                <button key={a.label} className="gs-act" onClick={a.onClick} style={{ border: `1px solid ${a.border}`, background: a.bg, color: a.fg, font: "700 11px 'Hanken Grotesk'", letterSpacing: '.01em', padding: '4px 8px', borderRadius: 6 }}>{a.label}</button>
              ))
            )}
            {onChallenge && !dec && (
              <button onClick={onChallenge} style={{ border: '1px solid #E1E4E9', background: '#F4F6F8', color: '#41464F', font: "700 11px 'Hanken Grotesk'", letterSpacing: '.01em', padding: '4px 8px', borderRadius: 6, cursor: 'pointer' }}>Challenge Review</button>
            )}
          </div>
        </div>
      </div>

      {/* decision banner */}
      {dec && decMeta && (
        <div style={{ background: decMeta.bg, borderBottom: `1px solid ${decMeta.border}`, padding: '9px 18px', font: "600 12px 'Hanken Grotesk'", color: decMeta.color, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span>● Decision recorded:</span><span style={{ fontFamily: "'JetBrains Mono'", fontWeight: 500 }}>{dec.action} · D. Mihajlović · {dec.ts}</span>
        </div>
      )}

      <div style={{ padding: '16px 18px 28px', maxWidth: 1320, margin: '0 auto' }}>

        {/* cause banner */}
        <div style={{ background: '#fff', border: '1px solid #E1E4E9', borderLeft: `4px solid ${avm.color}`, borderRadius: 11, padding: '14px 17px', marginBottom: 14, boxShadow: '0 1px 2px rgba(20,23,28,0.03)' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
            <span style={{ font: "700 13px 'Hanken Grotesk'", color: avm.color, letterSpacing: '.01em' }}>{ac.causeHead}</span>
            {acomp != null && (
              <span style={{ font: "500 12px 'JetBrains Mono'", color: '#757B86' }}>R = <b style={{ color: '#14171C' }}>{acomp.toFixed(2)}</b> · REVIEW threshold {ac.threshold.toFixed(2)}</span>
            )}
          </div>
          <p style={{ margin: '8px 0 0', font: "400 12.5px/1.6 'Hanken Grotesk'", color: '#41464F', maxWidth: 1060 }}>{ac.causeBody}</p>
        </div>

        {/* three-band */}
        <div style={{ display: 'grid', gridTemplateColumns: '312px minmax(0,1fr) 334px', gap: 14, alignItems: 'start' }}>

          {/* LEFT: PAYMENT */}
          <div style={{ background: '#fff', border: '1px solid #E1E4E9', borderRadius: 12, boxShadow: '0 1px 2px rgba(20,23,28,0.03)' }}>
            <div style={{ font: "700 11px 'Hanken Grotesk'", letterSpacing: '.08em', textTransform: 'uppercase', color: '#757B86', padding: '13px 15px', borderBottom: '1px solid #EEF0F3' }}>Payment instruction</div>
            <div style={{ padding: 15 }}>
              <div style={{ background: '#F7F8FA', border: '1px solid #EEF0F3', borderRadius: 9, padding: '12px 13px', marginBottom: 14 }}>
                <div style={{ font: "700 22px 'JetBrains Mono'", letterSpacing: '-0.02em', color: '#14171C' }}>{ac.pay.amount}</div>
                <div style={{ font: "500 11px 'JetBrains Mono'", color: '#757B86', marginTop: 3 }}>{ac.pay.amountSub} · {ac.pay.corridor}</div>
              </div>
              <div style={{ font: "700 9px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.07em', marginBottom: 6 }}>Originator</div>
              <div style={{ font: "600 13px 'Hanken Grotesk'", color: '#14171C' }}>{ac.pay.senderName}</div>
              <div style={{ font: "500 11px 'JetBrains Mono'", color: '#757B86', margin: '3px 0 8px' }}>{ac.pay.senderWallet}</div>
              <span style={{ display: 'inline-flex', alignItems: 'center', font: "600 10px 'JetBrains Mono'", color: sUbo.color, background: sUbo.bg, border: `1px solid ${sUbo.border}`, borderRadius: 6, padding: '3px 8px' }}>UBO {ac.pay.senderUbo}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, margin: '15px 0' }}>
                <div style={{ flex: 1, height: 1, background: '#EEF0F3' }} />
                <span style={{ font: "600 10px 'JetBrains Mono'", color: '#B4BAC2' }}>▼ {ac.pay.rail}</span>
                <div style={{ flex: 1, height: 1, background: '#EEF0F3' }} />
              </div>
              <div style={{ font: "700 9px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.07em', marginBottom: 6 }}>Beneficiary</div>
              <div style={{ font: "600 13px 'Hanken Grotesk'", color: '#14171C' }}>{ac.pay.receiverName}</div>
              <div style={{ font: "500 11px 'JetBrains Mono'", color: '#757B86', margin: '3px 0 8px' }}>{ac.pay.receiverWallet}</div>
              <span style={{ display: 'inline-flex', alignItems: 'center', font: "600 10px 'JetBrains Mono'", color: rUbo.color, background: rUbo.bg, border: `1px solid ${rUbo.border}`, borderRadius: 6, padding: '3px 8px' }}>UBO {ac.pay.receiverUbo}</span>
              {(ac.pay.tags || []).length > 0 && (
                <div style={{ marginTop: 15, paddingTop: 14, borderTop: '1px solid #EEF0F3', display: 'flex', flexDirection: 'column', gap: 9 }}>
                  {ac.pay.tags.map(tg => {
                    const fm = flagMeta(tg.k === 'UBO' ? 'UBO' : (tg.k === 'CLUSTER' ? 'CLUSTER' : 'INFO'));
                    const tagColor = tg.k === 'BLACK' ? '#14171C' : (tg.k === 'INT' ? '#6B7280' : fm.color);
                    return (
                      <div key={tg.k} style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
                        <span style={{ width: 8, height: 8, borderRadius: 3, background: tagColor, marginTop: 3, flex: '0 0 auto' }} />
                        <div>
                          <div style={{ font: "600 11px 'JetBrains Mono'", color: tagColor }}>{tg.label}</div>
                          <div style={{ font: "400 10.5px/1.45 'Hanken Grotesk'", color: '#757B86', marginTop: 2 }}>{tg.note}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* CENTER: WATERFALL */}
          <div style={{ background: '#fff', border: '1px solid #E1E4E9', borderRadius: 12, boxShadow: '0 1px 2px rgba(20,23,28,0.03)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 15px', borderBottom: '1px solid #EEF0F3' }}>
              <span style={{ font: "700 11px 'Hanken Grotesk'", letterSpacing: '.08em', textTransform: 'uppercase', color: '#757B86' }}>Risk score waterfall · Track B</span>
              <span style={{ font: "500 10px 'JetBrains Mono'", color: '#9AA0AA' }}>6 factors · weighted additive</span>
            </div>
            {factors.length > 0 ? (
              <div style={{ padding: 15 }}>
                <div style={{ position: 'relative', height: 32, background: '#F4F6F8', borderRadius: 8, overflow: 'hidden', display: 'flex' }}>
                  {factors.map(f => (
                    <div key={f.name} title={f.name} style={{ height: '100%', width: `${f.contribPct}%`, background: f.tintColor, borderRight: '1.5px solid #fff' }} />
                  ))}
                  <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 0, borderLeft: '2px dashed #14171C' }} />
                  <div style={{ position: 'absolute', left: '50%', top: 3, transform: 'translateX(5px)', font: "700 9px 'JetBrains Mono'", color: '#14171C' }}>0.50</div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', font: "500 10px 'JetBrains Mono'", color: '#9AA0AA', margin: '6px 2px 0' }}>
                  <span>0.00</span>
                  <span style={{ color: avm.color, fontWeight: 700 }}>▲ R = {acomp?.toFixed(2)}</span>
                  <span>1.00</span>
                </div>
                <div style={{ marginTop: 15 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 92px 50px 60px', gap: 10, font: "700 9px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.05em', paddingBottom: 7, borderBottom: '1px solid #EEF0F3' }}>
                    <div>Factor</div><div>Score</div><div style={{ textAlign: 'center' }}>Weight</div><div style={{ textAlign: 'right' }}>Contrib.</div>
                  </div>
                  {factors.map(f => (
                    <div key={f.name} style={{ padding: '11px 0', borderBottom: '1px solid #F4F6F8' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 92px 50px 60px', gap: 10, alignItems: 'center' }}>
                        <div style={{ font: "600 12.5px 'Hanken Grotesk'", color: '#14171C' }}>{f.name}</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                          <span style={{ font: "600 11px 'JetBrains Mono'", color: '#41464F', width: 26 }}>{f.scoreStr}</span>
                          <div style={{ flex: 1, height: 5, background: '#EEF0F3', borderRadius: 3, overflow: 'hidden' }}><div style={{ height: '100%', width: `${f.scoreW}%`, background: f.tintColor }} /></div>
                        </div>
                        <div style={{ textAlign: 'center', font: "500 11px 'JetBrains Mono'", color: '#9AA0AA' }}>{f.weightStr}</div>
                        <div style={{ textAlign: 'right', font: "700 11px 'JetBrains Mono'", color: '#14171C' }}>{f.contribStr}</div>
                      </div>
                      <p style={{ margin: '7px 0 0', font: "400 11.5px/1.55 'Hanken Grotesk'", color: '#6B717B' }}>{f.detail}</p>
                      {f.sub && f.sub.length > 0 && (
                        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 5, paddingLeft: 11, borderLeft: '2px solid #EEF0F3' }}>
                          {f.sub.map(sb => (
                            <div key={sb.l} style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                              <span style={{ font: "600 10.5px 'JetBrains Mono'", color: '#41464F', width: 108, flex: '0 0 auto' }}>{sb.l}</span>
                              <span style={{ font: "600 10.5px 'JetBrains Mono'", color: sb.tintColor, width: 34 }}>{sb.sStr}</span>
                              <span style={{ font: "400 10.5px 'Hanken Grotesk'", color: '#9AA0AA' }}>{sb.d}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ padding: '30px 16px', textAlign: 'center' }}>
                <div style={{ font: "600 13px 'Hanken Grotesk'", color: '#41464F' }}>{ac.noFactorsHead}</div>
                <p style={{ margin: '8px auto 0', maxWidth: 380, font: "400 11.5px/1.55 'Hanken Grotesk'", color: '#9AA0AA' }}>{ac.noFactorsBody}</p>
              </div>
            )}
          </div>

          {/* RIGHT: PROFILE */}
          <div style={{ background: '#fff', border: '1px solid #E1E4E9', borderRadius: 12, boxShadow: '0 1px 2px rgba(20,23,28,0.03)' }}>
            <div style={{ font: "700 11px 'Hanken Grotesk'", letterSpacing: '.08em', textTransform: 'uppercase', color: '#757B86', padding: '13px 15px', borderBottom: '1px solid #EEF0F3' }}>Entity profile</div>
            <div style={{ padding: 15 }}>
              {profileRows.map(p => (
                <div key={p.k} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '6px 0', borderBottom: '1px solid #F4F6F8' }}>
                  <span style={{ font: "500 11px 'Hanken Grotesk'", color: '#9AA0AA', flex: '0 0 auto' }}>{p.k}</span>
                  <span style={{ font: "600 11.5px 'JetBrains Mono'", color: '#14171C', textAlign: 'right' }}>{p.v}</span>
                </div>
              ))}
              <div style={{ marginTop: 13, background: '#F7F8FA', border: '1px solid #EEF0F3', borderRadius: 9, padding: '11px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ font: "700 9px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.07em' }}>UBO resolution</span>
                  <span style={{ font: "700 10px 'Hanken Grotesk'", color: um.color, background: um.bg, border: `1px solid ${um.border}`, borderRadius: 5, padding: '2px 7px' }}>{ac.profile.uboStatus}</span>
                </div>
                <div style={{ font: "600 12px 'Hanken Grotesk'", color: '#14171C', marginTop: 7 }}>{ac.profile.uboName}</div>
                <div style={{ font: "500 10.5px 'JetBrains Mono'", color: '#9AA0AA', marginTop: 2 }}>depth {ac.profile.uboDepth}</div>
                <p style={{ margin: '7px 0 0', font: "400 11px/1.5 'Hanken Grotesk'", color: '#6B717B' }}>{ac.profile.uboDetail}</p>
              </div>
              <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#F7F8FA', border: '1px solid #EEF0F3', borderRadius: 9, padding: '10px 12px' }}>
                <div>
                  <div style={{ font: "700 9px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.07em' }}>KYB wallet registry</div>
                  <div style={{ font: "500 11px 'JetBrains Mono'", color: '#41464F', marginTop: 3 }}>{ac.profile.kybAddress}</div>
                </div>
                <span style={{ font: "700 10px 'Hanken Grotesk'", color: km.color, background: km.bg, border: `1px solid ${km.border}`, borderRadius: 5, padding: '3px 7px' }}>{ac.profile.kybStatus}</span>
              </div>
              {(ac.profile.corpFlags || []).length > 0 && (
                <div style={{ marginTop: 13 }}>
                  <div style={{ font: "700 9px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.07em', marginBottom: 7 }}>Corporate risk signals</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                    {ac.profile.corpFlags.map(cf => (
                      <span key={cf} style={{ font: "500 10px 'JetBrains Mono'", color: '#B23A1E', background: '#FBEEE8', border: '1px solid #F2D2C4', borderRadius: 5, padding: '3px 7px' }}>+ {cf}</span>
                    ))}
                  </div>
                </div>
              )}
              {adverse.length > 0 && (
                <div style={{ marginTop: 13 }}>
                  <div style={{ font: "700 9px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.07em', marginBottom: 7 }}>Adverse media · LLM relevance</div>
                  {adverse.map(am => (
                    <div key={am.src + am.date} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 0' }}>
                      <span style={{ font: "500 11px 'Hanken Grotesk'", color: '#41464F' }}>{am.src} · {am.date}</span>
                      <span style={{ font: "600 11px 'JetBrains Mono'", color: am.tintColor }}>{am.relStr}</span>
                    </div>
                  ))}
                </div>
              )}
              <div style={{ marginTop: 13, paddingTop: 12, borderTop: '1px solid #EEF0F3' }}>
                <div style={{ font: "700 9px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.07em', marginBottom: 5 }}>Historical flag rate · Beta(1,9)</div>
                <div style={{ font: "500 11px 'JetBrains Mono'", color: '#41464F' }}>{histFraction}</div>
              </div>
            </div>
          </div>
        </div>

        {/* NETWORK */}
        {net && (
          <div style={{ background: '#fff', border: '1px solid #E1E4E9', borderRadius: 12, marginTop: 14, boxShadow: '0 1px 2px rgba(20,23,28,0.03)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 15px', borderBottom: '1px solid #EEF0F3' }}>
              <span style={{ font: "700 11px 'Hanken Grotesk'", letterSpacing: '.08em', textTransform: 'uppercase', color: '#757B86' }}>
                {netNoisy ? 'Network exposure · noisy-OR' : netOwnership ? 'Ownership chain · 50% Rule' : 'Cluster context · shared UBO'}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ font: "500 10px 'JetBrains Mono'", color: '#9AA0AA' }}>{net.id}</span>
                {onOpenNetwork && (
                  <button onClick={onOpenNetwork} style={{ background: '#F0F4FF', color: '#2C7BE5', border: '1px solid #C7D8F8', borderRadius: 6, font: "600 10px 'Hanken Grotesk'", padding: '4px 9px', cursor: 'pointer' }}>
                    Full Graph →
                  </button>
                )}
              </div>
            </div>
            <div style={{ padding: '18px 16px' }}>
              {netNoisy && (
                <>
                  <div style={{ display: 'flex', alignItems: 'stretch', justifyContent: 'center', gap: 0, flexWrap: 'nowrap' }}>
                    {noisyNodes.map((n, i) => (
                      <div key={n.id} style={{ display: 'flex', alignItems: 'stretch', flex: n.hasConnector ? undefined : '1' }}>
                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', maxWidth: 300 }}>
                          <div style={{ font: "600 9px 'JetBrains Mono'", color: '#9AA0AA', marginBottom: 9 }}>hop {n.hop}</div>
                          <div style={{ width: 46 + n.taint * 30, height: 46 + n.taint * 30, borderRadius: '50%', background: n.bg, border: `2.5px solid ${n.col}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto', boxShadow: `0 4px 14px -4px ${n.glow}` }}>
                            <span style={{ font: "700 12px 'JetBrains Mono'", color: n.col }}>{n.taintStr}</span>
                          </div>
                          <div style={{ font: "700 12px 'Hanken Grotesk'", color: '#14171C', marginTop: 10 }}>{n.label}</div>
                          <div style={{ font: "500 10px 'JetBrains Mono'", color: '#9AA0AA', marginTop: 2 }}>{n.sub}</div>
                          {n.hop !== 0 && (
                            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'center' }}>
                              <span style={{ font: "600 10px 'JetBrains Mono'", color: '#41464F', background: '#F4F6F8', borderRadius: 5, padding: '3px 8px' }}>shares {n.shared}</span>
                              <span style={{ font: "600 10px 'JetBrains Mono'", color: n.col }}>+{n.contribStr} to noisy-OR</span>
                              <span style={{ font: "500 9.5px 'JetBrains Mono'", color: '#9AA0AA' }}>leave-one-out {n.marginalStr}</span>
                            </div>
                          )}
                        </div>
                        {n.hasConnector && (
                          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-start', flex: '0 0 66px', paddingTop: 34 }}>
                            <div style={{ font: "600 9px 'JetBrains Mono'", color: '#B4BAC2', marginBottom: 4 }}>{n.edgeDecay}</div>
                            <div style={{ width: '100%', height: 0, borderTop: '2px dashed #CDD2D9' }} />
                            <div style={{ font: "600 11px 'JetBrains Mono'", color: '#B4BAC2', marginTop: 2 }}>→</div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: 18, background: '#F7F8FA', border: '1px solid #EEF0F3', borderRadius: 9, padding: '12px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
                    <div>
                      <div style={{ font: "700 9px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.07em' }}>noisy-OR · 1 − ∏ (1 − pₓ·λᵈ)</div>
                      <div style={{ font: "600 12px 'JetBrains Mono'", color: '#14171C', marginTop: 5 }}>{net.formula}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ font: "700 21px 'JetBrains Mono'", color: avm.color, lineHeight: 1 }}>{net.risk?.toFixed(3)}</div>
                      <div style={{ font: "500 10px 'Hanken Grotesk'", color: '#9AA0AA', marginTop: 3 }}>→ REVIEW · not blocked on association</div>
                    </div>
                  </div>
                </>
              )}
              {netOwnership && (
                <>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0 }}>
                    {ownerChain.map((c, i) => (
                      <div key={i}>
                        <div style={{ width: '100%', maxWidth: 440, background: c.bg, border: `1.5px solid ${c.border}`, borderRadius: 10, padding: '11px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <div>
                            <div style={{ font: "600 13px 'Hanken Grotesk'", color: c.ink }}>{c.label}</div>
                            <div style={{ font: "500 10.5px 'JetBrains Mono'", color: c.sub2, marginTop: 2 }}>{c.sub}</div>
                          </div>
                          {c.pct && <span style={{ font: "700 13px 'JetBrains Mono'", color: c.ink }}>{c.pct}</span>}
                        </div>
                        {c.hasArrow && <div style={{ font: "600 12px 'JetBrains Mono'", color: '#B4BAC2', padding: '4px 0', textAlign: 'center' }}>↓ owned by</div>}
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: 16, background: '#FCEBEB', border: '1px solid #F3C9C9', borderRadius: 9, padding: '12px 14px', textAlign: 'center', font: "700 12.5px 'Hanken Grotesk'", color: '#DC2626' }}>{net.effective}</div>
                </>
              )}
              {netCluster && (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
                    {clusterNodes.map(cl => (
                      <div key={cl.label} style={{ background: cl.bg, border: `1.5px solid ${cl.border}`, borderRadius: 10, padding: 12, textAlign: 'center' }}>
                        <div style={{ width: 14, height: 14, borderRadius: '50%', background: cl.dot, margin: '0 auto 9px' }} />
                        <div style={{ font: "600 12px 'Hanken Grotesk'", color: '#14171C', lineHeight: 1.25 }}>{cl.label}</div>
                        <div style={{ font: "500 10px 'JetBrains Mono'", color: '#9AA0AA', marginTop: 4 }}>{cl.sub}</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: 16, background: '#F1EAFB', border: '1px solid #DDC9F5', borderRadius: 9, padding: '12px 14px', textAlign: 'center', font: "600 12.5px 'Hanken Grotesk'", color: '#7C3AED' }}>{net.shadow}</div>
                </>
              )}
            </div>
          </div>
        )}

        {/* AUDIT */}
        <div style={{ background: '#fff', border: '1px solid #E1E4E9', borderRadius: 12, marginTop: 14, boxShadow: '0 1px 2px rgba(20,23,28,0.03)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 15px', borderBottom: '1px solid #EEF0F3' }}>
            <span style={{ font: "700 11px 'Hanken Grotesk'", letterSpacing: '.08em', textTransform: 'uppercase', color: '#757B86' }}>Audit record · machine proposes, human disposes</span>
            <span style={{ font: "500 10px 'JetBrains Mono'", color: '#9AA0AA' }}>editable draft · who / what / when / why</span>
          </div>
          <div style={{ padding: 15 }}>
            <textarea
              value={auditValue}
              onChange={e => setDraft(ac.id, e.target.value)}
              spellCheck={false}
              style={{ width: '100%', minHeight: 112, resize: 'vertical', border: '1px solid #E1E4E9', borderRadius: 9, background: '#FAFBFC', padding: 13, font: "500 12px/1.65 'JetBrains Mono'", color: '#14171C', outline: 'none' }}
            />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 11, flexWrap: 'wrap', gap: 10 }}>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {['algorithm v1.1', 'OFAC 2026-06-12', 'EU 2026-06-11', 'retention 5y'].map(tag => (
                  <span key={tag} style={{ font: "500 10px 'JetBrains Mono'", color: '#757B86', background: '#F4F6F8', borderRadius: 5, padding: '4px 8px' }}>{tag}</span>
                ))}
              </div>
              <span style={{ font: "400 11px 'Hanken Grotesk'", color: '#9AA0AA' }}>Pre-populated by LLM explanation · analyst edits &amp; confirms on decision</span>
            </div>
          </div>
        </div>

      </div>
    </main>
  );
}
