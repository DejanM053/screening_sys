import { useState, useEffect, useCallback, useRef } from 'react';
import { QueueDashboard } from './pages/QueueDashboard';
import { CaseDetail } from './pages/CaseDetail';
import { ChallengeReviewPanel } from './components/ChallengeReviewPanel';
import { NetworkExplorer } from './pages/NetworkExplorer';
import { screeningApi, QueueItem, Explanation } from './api/screening';
import { Case, Factor } from './data/cases';

export type View = 'queue' | 'case' | 'network';

// ─── Factor metadata ─────────────────────────────────────────────────────────

const FACTOR_IDS   = ['identity_match','behavioral_anomaly','network_exposure','entity_risk_profile','doc_integrity','historical_flag_rate'];
const FACTOR_NAMES = ['Identity match signal','Behavioral / txn anomaly','Network / graph exposure','Entity risk profile','Document / onboarding integrity','Historical flag rate'];
const FACTOR_W     = [0.25, 0.20, 0.20, 0.15, 0.10, 0.10];
const FACTOR_DETAILS = [
  'RapidFuzz composite (Jaro-Winkler + token-sort) against OFAC SDN, EU Consolidated, UN, HMT. Partial alias matches and transliteration variants included.',
  'Transaction amount, velocity, and corridor pattern assessed against peer-entity baseline. Structuring indicators and round-number anomalies flagged.',
  'Noisy-OR network risk over ownership graph (λ=0.5 per hop, capped at 3). Per-neighbour leave-one-out attribution — see network panel for hop detail.',
  'Jurisdiction tier, UBO opacity score, registration age, corporate structure complexity, and adverse media signals aggregated into entity-level risk index.',
  'Onboarding documentation completeness and consistency checked against submitted KYB package. Secondary verification pending for beneficial owner certificates.',
  'Beta-Binomial posterior on prior screening history. Prior screenings and flag events update the flag-rate estimate with smoothing prior (α=1, β=9).',
];

// ─── Country → tier ──────────────────────────────────────────────────────────

function countryTier(country: string): string {
  const c = country.toUpperCase();
  if (/IRAN|NORTH.KOREA|MYANMAR|CUBA|SYRIA/.test(c)) return 'BLACK';
  if (/UAE|UNITED.ARAB|RUSSIA|PAKISTAN|NIGERIA|KENYA|GHANA|SOUTH.AFRICA|CAYMAN|BVI|PANAMA/.test(c)) return 'GREY';
  if (/SEYCHELLES|VANUATU|MARSHALL|SAMOA|ANGUILLA|NEVIS/.test(c)) return 'OFFSHORE';
  return 'STANDARD';
}

// ─── Adapter: QueueItem + Explanation → Case ─────────────────────────────────

function queueItemToCase(item: QueueItem, exp: Explanation | null): Case {
  const tree      = exp?.tree;
  const children  = tree?.children ?? [];
  const getNode   = (id: string) => children.find(n => n.id === id);

  const score      = exp?.composite_score ?? item.score ?? 0;
  const trackStr   = exp?.track ?? item.track ?? 'B:risk';
  const isTrackA     = trackStr.startsWith('A:');
  const isHardMatchA = trackStr === 'A:identity' || trackStr === 'A:country-sanctions' || trackStr === 'A:50-rule';

  const factors: Factor[] | undefined = exp
    ? FACTOR_IDS.map((id, i) => {
        const node = getNode(id);
        return {
          name:   FACTOR_NAMES[i],
          score:  node?.score ?? 0,
          weight: node?.weight ?? FACTOR_W[i],
          detail: node?.detail || FACTOR_DETAILS[i],
        };
      })
    : isHardMatchA
      ? undefined
      : FACTOR_IDS.map((id, i) => ({
          name:   FACTOR_NAMES[i],
          score,
          weight: FACTOR_W[i],
          detail: FACTOR_DETAILS[i],
        }));
  const verdictStr: 'MATCH' | 'REVIEW' | 'NO_MATCH' = exp?.verdict
    ? (exp.verdict as 'MATCH' | 'REVIEW' | 'NO_MATCH')
    : trackStr.startsWith('A:country') || trackStr.startsWith('A:identity') || trackStr.startsWith('A:50')
      ? 'MATCH'
      : trackStr.startsWith('A:partial') || score >= 0.50
        ? 'REVIEW'
        : 'NO_MATCH';
  const slaMins    = item.sla_deadline
    ? Math.max(0, Math.round((new Date(item.sla_deadline).getTime() - Date.now()) / 60000))
    : 60;

  const pay        = exp?.payment ?? {};
  const origName   = pay.originator_name ?? item.entity_name;
  const benefName  = pay.beneficiary_name ?? '';
  const origCtry   = pay.originator_country ?? item.country ?? '';
  const benefCtry  = pay.beneficiary_country ?? item.country ?? '';
  const amountUsd  = pay.amount_usd ?? item.amount_usd ?? 0;
  const assetType  = pay.asset_type ?? 'fiat';
  const isCrypto   = /crypto|tron|usdt|btc|eth/i.test(assetType);

  const rail       = isCrypto ? 'TRON · USDT' : 'Wire transfer (SWIFT)';
  const corridor   = `${origCtry || '?'} → ${benefCtry || '?'}`;
  const uboStatus  = item.ubo_resolution_status ?? 'UNRESOLVED';
  const lists      = (item.lists_flagged ?? []).join('; ') || '—';
  const flags      = item.policy_flags ?? [];

  const causeRoot  = tree?.detail ?? '';
  const trackLong  = trackStr.startsWith('A:') ? `Track A — ${trackStr.slice(2)}` :
                     trackStr.startsWith('B:') ? `Track B — ${trackStr.slice(2)}` : trackStr;
  const llmText    = exp?.llm_explanation ?? '';

  const verdict_display = verdictStr === 'MATCH' ? 'MATCH — payment blocked'
    : verdictStr === 'REVIEW' ? 'REVIEW — routed to human review'
    : 'NO_MATCH — cleared';

  return {
    id:          item.payment_id,
    entity:      origName,
    entityType:  'business (KYB)',
    verdict:     verdictStr,
    track:       trackStr,
    trackLong:   trackLong,
    threshold:   0.50,
    country:     benefCtry || origCtry || item.country || '',
    tier:        countryTier(benefCtry || origCtry || item.country || ''),
    transfer:    item.transfer_type ?? 'OUTBOUND',
    lists,
    slaMins,
    flags,
    causeHead:   `${verdict_display} · ${trackStr}`,
    causeBody:   llmText || causeRoot || `Composite score ${score.toFixed(2)} vs threshold 0.50.`,
    composite:   score,
    pay: {
      amount:       amountUsd > 0 ? `$${amountUsd.toLocaleString('en-US')}` : '—',
      amountSub:    amountUsd > 0 ? `USD ${amountUsd.toLocaleString('en-US')}` : '—',
      corridor,
      rail,
      senderName:   origName,
      senderWallet: '',
      senderUbo:    'FULL',
      receiverName: benefName || '—',
      receiverWallet: '',
      receiverUbo:  uboStatus,
      tags: flags.map(f => ({ k: f, label: f, note: '' })),
    },
    factors: isHardMatchA ? undefined : factors,
    noFactorsHead: isHardMatchA ? 'Risk score not used for this verdict' : undefined,
    noFactorsBody: isHardMatchA ? 'This verdict is a deterministic Track A decision.' : undefined,
    network: null,
    profile: {
      regNo:       '',
      incorporated: '',
      jurisdiction: benefCtry || origCtry || item.country || '',
      structure:   'Unknown',
      uboStatus,
      uboDepth:    '',
      uboName:     '',
      uboDetail:   `UBO resolution status: ${uboStatus}.`,
      kybStatus:   uboStatus === 'FULL' ? 'FULL' : 'PARTIAL',
      kybAddress:  '',
      corpFlags:   [],
      adverse:     [],
      histScreen:  0,
      histHits:    0,
      histRate:    '0.000',
    },
    audit: llmText || causeRoot || `${verdict_display}. Score: ${score.toFixed(3)}. Track: ${trackStr}.`,
  };
}

// ─── App ─────────────────────────────────────────────────────────────────────

export default function App() {
  const [view, setView]           = useState<View>('queue');
  const [activeId, setActiveId]   = useState<string | null>(null);
  const [tFilter, setTFilter]     = useState('all');
  const [vFilter, setVFilter]     = useState('all');
  const [drafts, setDrafts]       = useState<Record<string, string>>({});
  const [decisions, setDecisions] = useState<Record<string, { action: string; ts: string }>>({});
  const [showChallenge, setShowChallenge]     = useState(false);
  const [openChallengeIds, setOpenChallengeIds] = useState<string[]>([]);

  // Real API state
  const [queueItems, setQueueItems]         = useState<QueueItem[]>([]);
  const [decidedItems, setDecidedItems]     = useState<QueueItem[]>([]);
  const [explanations, setExplanations]     = useState<Record<string, Explanation | null>>({});
  const [loading, setLoading]               = useState(true);
  const [error, setError]                   = useState<string | null>(null);
  const activeIdRef = useRef(activeId);
  activeIdRef.current = activeId;

  const fetchQueue = useCallback(async () => {
    try {
      const [pending, decided] = await Promise.all([
        screeningApi.getQueue(),
        screeningApi.getDecidedQueue(),
      ]);
      setQueueItems(pending);
      setDecidedItems(decided);
      const decMap: Record<string, { action: string; ts: string }> = {};
      decided.forEach(item => {
        if (item.decision && item.decided_at) {
          decMap[item.payment_id] = { action: item.decision, ts: item.decided_at };
        }
      });
      setDecisions(prev => ({ ...decMap, ...prev }));
      setError(null);
      if (!activeIdRef.current && pending.length > 0) {
        setActiveId(pending[0].payment_id);
      }
    } catch {
      setError('Queue unavailable — check that review-queue service is running on port 8009.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
    const t = setInterval(fetchQueue, 30_000);
    return () => clearInterval(t);
  }, [fetchQueue]);

  // Lazy-fetch explanation when a case is activated
  useEffect(() => {
    if (!activeId) return;
    if (Object.prototype.hasOwnProperty.call(explanations, activeId)) return;
    // Mark as in-flight so we don't double-fetch
    setExplanations(prev => ({ ...prev, [activeId]: null }));
    screeningApi.getExplanation(activeId).then(exp => {
      setExplanations(prev => ({ ...prev, [activeId]: exp }));
    });
  }, [activeId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Convert live queue items into Case objects for existing UI components
  const cases: Case[] = queueItems.map(item =>
    queueItemToCase(item, explanations[item.payment_id] ?? null)
  );

  const decidedCases: Case[] = decidedItems.map(item =>
    queueItemToCase(item, explanations[item.payment_id] ?? null)
  );

  const activeCase = cases.find(c => c.id === activeId) ?? decidedCases.find(c => c.id === activeId) ?? null;

  const goCase = (id: string) => { setActiveId(id); setView('case'); };
  const goQueue = () => { setView('queue'); setShowChallenge(false); };
  const setDraft = (id: string, v: string) => setDrafts(d => ({ ...d, [id]: v }));
  const setDecision = (id: string, action: string) => {
    if (openChallengeIds.length > 0 && !window.confirm(
      'You have an open challenge on this case. Proceeding will record your verdict without a response. Continue?'
    )) return;
    const ts = new Date().toISOString().slice(0, 16).replace('T', ' ') + 'Z';
    setDecisions(d => ({ ...d, [id]: { action, ts } }));
    // Map button label to Decision enum value
    const decisionMap: Record<string, string> = {
      'CLEAR': 'CLEAR', 'BLOCK': 'BLOCK', 'ESCALATE': 'ESCALATE',
      'REQUEST INFO': 'REQUEST_INFO', 'DEFER': 'DEFER',
    };
    const decision = decisionMap[action] ?? action;
    screeningApi.postDecision(id, decision, 'DM').then(() => {
      // Refresh queue so decided item moves to the history section
      fetchQueue();
    }).catch(() => {
      // API call failed — local state already updated, UI remains consistent
    });
  };

  const isQueue   = view === 'queue';
  const isNetwork = view === 'network';

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#E8EAED' }}>

      {/* FLOATING NAV */}
      <div style={{ position: 'relative', zIndex: 30, padding: '13px 16px 9px', flex: '0 0 auto' }}>
        <header style={{ display: 'flex', alignItems: 'center', gap: 16, height: 56, padding: '0 10px 0 18px', borderRadius: 18, background: 'rgba(18,21,26,0.97)', backdropFilter: 'blur(14px)', border: '1px solid rgba(255,255,255,0.09)', boxShadow: '0 14px 34px -10px rgba(14,17,22,0.5),0 3px 8px rgba(14,17,22,0.22)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
            <div style={{ width: 24, height: 24, borderRadius: 7, border: '2px solid #fff', position: 'relative', flex: '0 0 auto' }}>
              <div style={{ position: 'absolute', inset: '3px 5px', borderBottom: '2px solid #fff', borderRadius: '0 0 5px 5px' }} />
            </div>
            <span style={{ fontWeight: 800, fontSize: 16, letterSpacing: '-0.01em', color: '#fff' }}>GuardScreen</span>
            <span style={{ font: '600 10px/1 \'JetBrains Mono\'', color: '#7E8590', border: '1px solid #2B313B', borderRadius: 5, padding: '4px 6px' }}>v1.1</span>
          </div>
          <div style={{ display: 'flex', gap: 3, marginLeft: 6, background: 'rgba(255,255,255,0.05)', padding: 4, borderRadius: 11, border: '1px solid rgba(255,255,255,0.05)' }}>
            <button className="gs-tab" onClick={goQueue} style={{ background: view === 'queue' ? '#fff' : 'transparent', color: view === 'queue' ? '#14171C' : '#9AA0AA', border: 'none', borderRadius: 8, font: '600 12.5px \'Hanken Grotesk\'', padding: '7px 14px', transition: 'all .12s' }}>Review Queue</button>
            <button className="gs-tab" onClick={() => setView('case')} style={{ background: view === 'case' ? '#fff' : 'transparent', color: view === 'case' ? '#14171C' : '#9AA0AA', border: 'none', borderRadius: 8, font: '600 12.5px \'Hanken Grotesk\'', padding: '7px 14px', transition: 'all .12s' }}>Case Detail</button>
            <button className="gs-tab" onClick={() => setView('network')} style={{ background: view === 'network' ? '#fff' : 'transparent', color: view === 'network' ? '#14171C' : '#9AA0AA', border: 'none', borderRadius: 8, font: '600 12.5px \'Hanken Grotesk\'', padding: '7px 14px', transition: 'all .12s' }}>Network Explorer</button>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 15, font: '500 11px \'JetBrains Mono\'', color: '#7E8590' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#16A34A', boxShadow: '0 0 0 3px rgba(22,163,74,0.18)' }} />
              <span>Lists current</span>
            </div>
            <span style={{ color: '#363C46' }}>·</span>
            <span>OFAC 06-12</span>
            <span style={{ color: '#363C46' }}>·</span>
            <span>EU 06-11</span>
            <div style={{ width: 1, height: 22, background: '#2B313B' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, color: '#C9CDD3', fontFamily: '\'Hanken Grotesk\'', fontSize: 12, fontWeight: 600 }}>
              <div style={{ width: 26, height: 26, borderRadius: 9, background: '#2C7BE5', display: 'flex', alignItems: 'center', justifyContent: 'center', font: '700 10px \'Hanken Grotesk\'', color: '#fff' }}>DM</div>
              <span>D. Mihajlović</span>
            </div>
          </div>
        </header>
      </div>

      {/* CONTENT */}
      {isNetwork ? (
        activeId && explanations[activeId] ? (
          <NetworkExplorer explanation={explanations[activeId]!} paymentId={activeId} />
        ) : (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
            <span style={{ font: "700 14px 'Hanken Grotesk'", color: '#14171C' }}>No case selected</span>
            <span style={{ font: "400 12px 'Hanken Grotesk'", color: '#757B86' }}>
              Open a case from the Review Queue first, then switch to Network Explorer.
            </span>
            <button onClick={goQueue} style={{ marginTop: 4, padding: '7px 18px', borderRadius: 9, border: '1px solid #E1E4E9', background: '#fff', font: "600 12px 'Hanken Grotesk'", cursor: 'pointer' }}>
              Go to Queue
            </button>
          </div>
        )
      ) : isQueue ? (
        loading ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', font: "600 14px 'Hanken Grotesk'", color: '#757B86' }}>
            Loading queue…
          </div>
        ) : error ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
            <span style={{ font: "700 14px 'Hanken Grotesk'", color: '#DC2626' }}>Queue unavailable</span>
            <span style={{ font: "400 12px 'Hanken Grotesk'", color: '#757B86', maxWidth: 480, textAlign: 'center' }}>{error}</span>
            <button onClick={fetchQueue} style={{ marginTop: 8, padding: '8px 18px', borderRadius: 9, border: '1px solid #E1E4E9', background: '#fff', font: "600 12px 'Hanken Grotesk'", cursor: 'pointer' }}>Retry</button>
          </div>
        ) : cases.length === 0 ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
            <span style={{ font: "700 14px 'Hanken Grotesk'", color: '#14171C' }}>Queue is empty</span>
            <span style={{ font: "400 12px 'Hanken Grotesk'", color: '#757B86' }}>No cases pending review. Run the seed script or screen new payments.</span>
          </div>
        ) : (
          <QueueDashboard
            cases={cases}
            decidedCases={decidedCases}
            decidedItems={decidedItems}
            tFilter={tFilter} setTFilter={setTFilter}
            vFilter={vFilter} setVFilter={setVFilter}
            onOpen={goCase}
          />
        )
      ) : (
        <>
          {activeCase ? (
            <CaseDetail
              cases={[...cases, ...decidedCases]}
              activeId={activeId!}
              drafts={drafts} setDraft={setDraft}
              decisions={decisions} setDecision={setDecision}
              onBack={goQueue}
              onChallenge={() => setShowChallenge(v => !v)}
              onOpenNetwork={() => setView('network')}
            />
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', font: "600 14px 'Hanken Grotesk'", color: '#757B86' }}>
              Select a case from the queue.
            </div>
          )}
          {showChallenge && activeId && (
            <ChallengeReviewPanel
              paymentId={activeId}
              caseData={activeCase ?? undefined}
              onClose={() => setShowChallenge(false)}
              onChallengeOpened={(id) => setOpenChallengeIds(ids => [...ids, id])}
              onChallengeResponded={(id) => setOpenChallengeIds(ids => ids.filter(x => x !== id))}
              onCaseEnqueued={() => { fetchQueue(); setShowChallenge(false); }}
            />
          )}
        </>
      )}
    </div>
  );
}
