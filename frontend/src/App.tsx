import { useState } from 'react';
import { DEMO_CASES } from './data/cases';
import { QueueDashboard } from './pages/QueueDashboard';
import { CaseDetail } from './pages/CaseDetail';
import { ChallengeReviewPanel } from './components/ChallengeReviewPanel';

export type View = 'queue' | 'case';

export default function App() {
  const [view, setView] = useState<View>('queue');
  const [activeId, setActiveId] = useState(DEMO_CASES[0].id);
  const [tFilter, setTFilter] = useState('all');
  const [vFilter, setVFilter] = useState('all');
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [decisions, setDecisions] = useState<Record<string, { action: string; ts: string }>>({});
  const [showChallenge, setShowChallenge] = useState(false);
  const [openChallengeIds, setOpenChallengeIds] = useState<string[]>([]);

  const goCase = (id: string) => { setActiveId(id); setView('case'); };
  const goQueue = () => { setView('queue'); setShowChallenge(false); };
  const setDraft = (id: string, v: string) => setDrafts(d => ({ ...d, [id]: v }));
  const setDecision = (id: string, action: string) => {
    if (openChallengeIds.length > 0 && !window.confirm(
      'You have an open challenge on this case. Proceeding will record your verdict without a response. Continue?'
    )) return;
    setDecisions(d => ({ ...d, [id]: { action, ts: new Date().toISOString().slice(0, 16).replace('T', ' ') + 'Z' } }));
  };

  const isQueue = view === 'queue';

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
            <button className="gs-tab" onClick={goQueue} style={{ background: isQueue ? '#fff' : 'transparent', color: isQueue ? '#14171C' : '#9AA0AA', border: 'none', borderRadius: 8, font: '600 12.5px \'Hanken Grotesk\'', padding: '7px 14px', transition: 'all .12s' }}>Review Queue</button>
            <button className="gs-tab" onClick={() => setView('case')} style={{ background: !isQueue ? '#fff' : 'transparent', color: !isQueue ? '#14171C' : '#9AA0AA', border: 'none', borderRadius: 8, font: '600 12.5px \'Hanken Grotesk\'', padding: '7px 14px', transition: 'all .12s' }}>Case Detail</button>
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

      {isQueue ? (
        <QueueDashboard
          cases={DEMO_CASES}
          tFilter={tFilter} setTFilter={setTFilter}
          vFilter={vFilter} setVFilter={setVFilter}
          onOpen={goCase}
        />
      ) : (
        <>
          <CaseDetail
            cases={DEMO_CASES}
            activeId={activeId}
            drafts={drafts} setDraft={setDraft}
            decisions={decisions} setDecision={setDecision}
            onBack={goQueue}
            onChallenge={() => setShowChallenge(v => !v)}
          />
          {showChallenge && (
            <ChallengeReviewPanel
              paymentId={activeId}
              onClose={() => setShowChallenge(false)}
              onChallengeOpened={(id) => setOpenChallengeIds(ids => [...ids, id])}
              onChallengeResponded={(id) => setOpenChallengeIds(ids => ids.filter(x => x !== id))}
            />
          )}
        </>
      )}
    </div>
  );
}
