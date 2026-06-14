// Place at: frontend/src/components/ChallengeReviewPanel.tsx
//
// MOUNTING POINT — in App.tsx, alongside the CaseDetail view:
//
//   import { ChallengeReviewPanel } from './components/ChallengeReviewPanel';
//
//   // In App() state:
//   const [showChallenge, setShowChallenge] = useState(false);
//   const [openChallengeIds, setOpenChallengeIds] = useState<string[]>([]);
//
//   // Modified setDecision (wraps the existing one):
//   const setDecisionWithWarning = (id: string, action: string) => {
//     if (openChallengeIds.length > 0) {
//       if (!window.confirm(
//         'You have an open challenge on this case. Proceeding will record your ' +
//         'verdict without a response. Continue?'
//       )) return;
//     }
//     setDecisions(d => ({ ...d, [id]: { action, ts: ... } }));
//   };
//
//   // In the case view render, alongside <CaseDetail ...>:
//   {!isQueue && (
//     <>
//       {/* existing CaseDetail */}
//       {showChallenge && (
//         <ChallengeReviewPanel
//           paymentId={activeId}
//           onClose={() => setShowChallenge(false)}
//           onChallengeOpened={(id) => setOpenChallengeIds(ids => [...ids, id])}
//           onChallengeResponded={(id) => setOpenChallengeIds(ids => ids.filter(x => x !== id))}
//         />
//       )}
//       <button onClick={() => setShowChallenge(v => !v)}>Challenge Review</button>
//     </>
//   )}

import { useState, useCallback, useEffect, useRef } from 'react';
import { challengeApi, SimilarCase, ChallengeResult, GeoContext } from '../api/challenge';

// ── Hardcoded geopolitical context (presenter: "pulled from live feeds in prod") ──
const GEO_TABLE: Record<string, Omit<GeoContext, never>> = {
  AE: { FATF_status: 'monitored',   basel_aml_index_score: 6.1, active_sanctions_programs: ['OFAC-GLOMAG'], export_control_alerts: ['BIS-MEP-2024-07: aluminum component diversion alert'] },
  CZ: { FATF_status: 'compliant',   basel_aml_index_score: 3.1, active_sanctions_programs: [], export_control_alerts: [] },
  DE: { FATF_status: 'compliant',   basel_aml_index_score: 2.9, active_sanctions_programs: [], export_control_alerts: [] },
  SG: { FATF_status: 'compliant',   basel_aml_index_score: 3.4, active_sanctions_programs: [], export_control_alerts: [] },
  CY: { FATF_status: 'compliant',   basel_aml_index_score: 5.1, active_sanctions_programs: [], export_control_alerts: [] },
  CH: { FATF_status: 'compliant',   basel_aml_index_score: 3.6, active_sanctions_programs: [], export_control_alerts: [] },
  US: { FATF_status: 'compliant',   basel_aml_index_score: 2.8, active_sanctions_programs: [], export_control_alerts: [] },
  MX: { FATF_status: 'monitored',   basel_aml_index_score: 6.1, active_sanctions_programs: [], export_control_alerts: [] },
  GB: { FATF_status: 'compliant',   basel_aml_index_score: 3.2, active_sanctions_programs: [], export_control_alerts: [] },
  IT: { FATF_status: 'compliant',   basel_aml_index_score: 3.8, active_sanctions_programs: [], export_control_alerts: [] },
  ML: { FATF_status: 'blacklisted', basel_aml_index_score: 8.4, active_sanctions_programs: ['EU-MALI-ARMS', 'UN-SC-2374'], export_control_alerts: [] },
  IE: { FATF_status: 'compliant',   basel_aml_index_score: 2.7, active_sanctions_programs: [], export_control_alerts: [] },
  RU: { FATF_status: 'blacklisted', basel_aml_index_score: 7.8, active_sanctions_programs: ['OFAC-SDN', 'EU-CONSOLIDATED'], export_control_alerts: ['BIS-EAR-RU: Russia export controls'] },
  CN: { FATF_status: 'monitored',   basel_aml_index_score: 5.9, active_sanctions_programs: [], export_control_alerts: [] },
  IR: { FATF_status: 'blacklisted', basel_aml_index_score: 9.1, active_sanctions_programs: ['OFAC-IRAN', 'EU-IRAN', 'UN-SC-1737'], export_control_alerts: [] },
};

const TYPOLOGY_TAGS = [
  'structuring','layering','trade_based_ml','pep_exposure',
  'sanctions_adjacent','crypto_layering','real_estate','correspondent_risk','unknown',
];

const VERDICT_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  approved:  { bg: '#E9F6EE', color: '#16A34A', label: 'APPROVED'  },
  blocked:   { bg: '#FCEBEB', color: '#DC2626', label: 'BLOCKED'   },
  escalated: { bg: '#FBF1E2', color: '#D97706', label: 'ESCALATED' },
};

const FATF_STYLE: Record<string, { bg: string; color: string }> = {
  compliant:   { bg: '#E9F6EE', color: '#16A34A' },
  monitored:   { bg: '#FBF1E2', color: '#D97706' },
  greylisted:  { bg: '#FEF3C7', color: '#B45309' },
  blacklisted: { bg: '#FCEBEB', color: '#DC2626' },
};

// ── Types ─────────────────────────────────────────────────────────────────────

type Step = 'form' | 'similar' | 'challenge';

interface Party {
  entity_name: string; entity_type: string;
  country_of_incorporation: string; account_country: string;
  registration_age_days: number; is_pep: boolean; ownership_opacity_score: number;
}

interface FormState {
  transaction_id: string; amount: string; currency: string;
  value_date: string; product_type: string; direction: string;
  originator: Party; beneficiary: Party;
  has_trade_context: boolean; goods_description: string; hs_code: string;
  dual_use_flag: boolean; invoice_amount: string; shipment_country: string;
  relationship_tenure_days: string; first_transaction_to_counterparty: boolean;
  referral_origin: string;
  typology_tags: string[]; reviewer_verdict: string; reviewer_rationale: string;
  risk_scores: { source_of_wealth: number; document_consistency: number; counterparty_opacity: number; relationship_novelty: number; };
}

const emptyParty = (): Party => ({
  entity_name: '', entity_type: 'company',
  country_of_incorporation: '', account_country: '',
  registration_age_days: 0, is_pep: false, ownership_opacity_score: 0.3,
});

const initialForm = (): FormState => ({
  transaction_id: '', amount: '', currency: 'EUR',
  value_date: new Date().toISOString().slice(0, 10),
  product_type: 'wire_transfer', direction: 'outbound',
  originator: emptyParty(), beneficiary: emptyParty(),
  has_trade_context: false, goods_description: '', hs_code: '',
  dual_use_flag: false, invoice_amount: '', shipment_country: '',
  relationship_tenure_days: '', first_transaction_to_counterparty: false,
  referral_origin: 'unknown',
  typology_tags: [], reviewer_verdict: 'blocked', reviewer_rationale: '',
  risk_scores: { source_of_wealth: 5, document_consistency: 5, counterparty_opacity: 5, relationship_novelty: 5 },
});

const DEMO_FORM: FormState = {
  transaction_id: 'REVIEW-TXN-' + Math.random().toString(36).slice(2, 7).toUpperCase(),
  amount: '3500000', currency: 'EUR',
  value_date: new Date().toISOString().slice(0, 10),
  product_type: 'trade_finance', direction: 'outbound',
  has_trade_context: true,
  goods_description: 'industrial valve components and hydraulic pressure systems',
  hs_code: '8481.80', dual_use_flag: true,
  invoice_amount: '3420000', shipment_country: 'AE',
  originator: {
    entity_name: 'Prague Industrial Exports s.r.o.',
    entity_type: 'company',
    country_of_incorporation: 'CZ', account_country: 'CZ',
    registration_age_days: 2920, is_pep: false, ownership_opacity_score: 0.18,
  },
  beneficiary: {
    entity_name: 'Al Mansouri General Trading LLC',
    entity_type: 'company',
    country_of_incorporation: 'AE', account_country: 'AE',
    registration_age_days: 210, is_pep: false, ownership_opacity_score: 0.62,
  },
  relationship_tenure_days: '30',
  first_transaction_to_counterparty: true,
  referral_origin: 'cold_contact',
  typology_tags: ['trade_based_ml', 'sanctions_adjacent'],
  reviewer_verdict: 'blocked',
  reviewer_rationale: 'New counterparty registered 7 months ago. Dual-use pressure valve components (HS 8481.80, Wassenaar-listed). No end-user certificate. AE re-export risk flagged by BIS MEP-2024-07. Blocking pending EUC and UBO verification.',
  risk_scores: { source_of_wealth: 5.0, document_consistency: 5.5, counterparty_opacity: 8.0, relationship_novelty: 9.5 },
};

// ── XML builder ───────────────────────────────────────────────────────────────

function escXml(s: string): string {
  return (s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function buildGeoSnapshot(countries: string[]): Record<string, GeoContext> {
  const snap: Record<string, GeoContext> = {};
  for (const cc of countries) {
    const upper = cc.toUpperCase();
    snap[upper] = GEO_TABLE[upper] ?? {
      FATF_status: 'compliant', basel_aml_index_score: 4.5,
      active_sanctions_programs: [], export_control_alerts: [],
    };
  }
  return snap;
}

function partyXml(tag: string, p: Party): string {
  return `    <${tag}>
      <entity_name>${escXml(p.entity_name)}</entity_name>
      <entity_type>${escXml(p.entity_type)}</entity_type>
      <country_of_incorporation>${escXml(p.country_of_incorporation)}</country_of_incorporation>
      <account_country>${escXml(p.account_country)}</account_country>
      <registration_age_days>${p.registration_age_days}</registration_age_days>
      <is_pep>${p.is_pep}</is_pep>
      <ownership_opacity_score>${p.ownership_opacity_score}</ownership_opacity_score>
    </${tag}>`;
}

function buildXml(f: FormState): string {
  const countries = [f.originator.country_of_incorporation, f.beneficiary.country_of_incorporation]
    .filter(Boolean).map(c => c.toUpperCase());
  const geo = buildGeoSnapshot(countries);

  const geoXml = Object.entries(geo).map(([cc, ctx]) => `
    <CountryContext country="${escXml(cc)}">
      <FATF_status>${escXml(ctx.FATF_status)}</FATF_status>
      <basel_aml_index_score>${ctx.basel_aml_index_score}</basel_aml_index_score>
      <ActiveSanctionsPrograms>${ctx.active_sanctions_programs.map(p => `<program>${escXml(p)}</program>`).join('')}</ActiveSanctionsPrograms>
      <ExportControlAlerts>${ctx.export_control_alerts.map(a => `<alert>${escXml(a)}</alert>`).join('')}</ExportControlAlerts>
    </CountryContext>`).join('');

  const tradeXml = f.has_trade_context && f.product_type === 'trade_finance'
    ? `<TradeContext present="true">
      <goods_description>${escXml(f.goods_description)}</goods_description>
      <hs_code>${escXml(f.hs_code)}</hs_code>
      <dual_use_flag>${f.dual_use_flag}</dual_use_flag>
      <invoice_amount>${f.invoice_amount || ''}</invoice_amount>
      <shipment_country>${escXml(f.shipment_country)}</shipment_country>
    </TradeContext>`
    : '<TradeContext present="false"/>';

  return `<?xml version="1.0" ?>
<AMLCase>
  <TransactionCore>
    <transaction_id>${escXml(f.transaction_id)}</transaction_id>
    <amount>${f.amount}</amount>
    <currency>${escXml(f.currency)}</currency>
    <value_date>${escXml(f.value_date)}</value_date>
    <product_type>${escXml(f.product_type)}</product_type>
    <direction>${escXml(f.direction)}</direction>
  </TransactionCore>
  <Parties>
${partyXml('Originator', f.originator)}
${partyXml('Beneficiary', f.beneficiary)}
  </Parties>
  ${tradeXml}
  <RelationshipContext>
    <relationship_tenure_days>${f.relationship_tenure_days || '0'}</relationship_tenure_days>
    <first_transaction_to_counterparty>${f.first_transaction_to_counterparty}</first_transaction_to_counterparty>
    <referral_origin>${escXml(f.referral_origin)}</referral_origin>
  </RelationshipContext>
  <AnalystAssessment>
    <TypologyTags>${f.typology_tags.map(t => `<tag>${escXml(t)}</tag>`).join('')}</TypologyTags>
    <RiskScores>
      <score key="source_of_wealth">${f.risk_scores.source_of_wealth}</score>
      <score key="document_consistency">${f.risk_scores.document_consistency}</score>
      <score key="counterparty_opacity">${f.risk_scores.counterparty_opacity}</score>
      <score key="relationship_novelty">${f.risk_scores.relationship_novelty}</score>
    </RiskScores>
    <reviewer_verdict>${escXml(f.reviewer_verdict)}</reviewer_verdict>
    <reviewer_rationale>${escXml(f.reviewer_rationale)}</reviewer_rationale>
  </AnalystAssessment>
  <GeopoliticalSnapshot>${geoXml}
  </GeopoliticalSnapshot>
</AMLCase>`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ title }: { title: string }) {
  return (
    <div style={{ font: "700 10px 'Hanken Grotesk'", letterSpacing: '.08em', textTransform: 'uppercase', color: '#9AA0AA', marginBottom: 10, paddingTop: 4 }}>
      {title}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 11 }}>
      <div style={{ font: "600 11px 'Hanken Grotesk'", color: '#757B86', marginBottom: 4 }}>{label}</div>
      {children}
    </div>
  );
}

const inp: React.CSSProperties = {
  width: '100%', border: '1px solid #E1E4E9', borderRadius: 7, padding: '7px 10px',
  font: "500 12px 'Hanken Grotesk'", color: '#14171C', background: '#FAFBFC',
  boxSizing: 'border-box', outline: 'none',
};

const sel: React.CSSProperties = { ...inp, appearance: 'none', WebkitAppearance: 'none', paddingRight: 28 };

function PartySection({ label, val, onChange }: { label: string; val: Party; onChange: (p: Party) => void }) {
  const f = (key: keyof Party) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    onChange({ ...val, [key]: e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value });
  const fNum = (key: keyof Party) => (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange({ ...val, [key]: parseFloat(e.target.value) || 0 });

  return (
    <div style={{ background: '#F7F8FA', border: '1px solid #EEF0F3', borderRadius: 9, padding: '12px 13px', marginBottom: 10 }}>
      <div style={{ font: "700 11px 'Hanken Grotesk'", color: '#41464F', marginBottom: 10 }}>{label}</div>
      <Field label="Entity name">
        <input style={inp} value={val.entity_name} onChange={f('entity_name')} placeholder="Full legal name" />
      </Field>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <Field label="Entity type">
          <select style={sel} value={val.entity_type} onChange={f('entity_type')}>
            <option value="company">Company</option>
            <option value="individual">Individual</option>
            <option value="financial_institution">Financial Institution</option>
          </select>
        </Field>
        <Field label="Country of incorporation">
          <input style={inp} value={val.country_of_incorporation} onChange={f('country_of_incorporation')} placeholder="ISO2 (AE, CZ…)" maxLength={2} />
        </Field>
        <Field label="Account country">
          <input style={inp} value={val.account_country} onChange={f('account_country')} placeholder="ISO2" maxLength={2} />
        </Field>
        <Field label="Entity age (days)">
          <input style={inp} type="number" value={val.registration_age_days} onChange={fNum('registration_age_days')} min={0} />
        </Field>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 4, marginBottom: 8 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, font: "500 12px 'Hanken Grotesk'", color: '#41464F', cursor: 'pointer' }}>
          <input type="checkbox" checked={val.is_pep} onChange={f('is_pep')} />
          PEP
        </label>
      </div>
      <Field label={`Ownership opacity ${val.ownership_opacity_score.toFixed(2)}`}>
        <input type="range" min={0} max={1} step={0.01} value={val.ownership_opacity_score}
          onChange={fNum('ownership_opacity_score')}
          style={{ width: '100%', accentColor: val.ownership_opacity_score > 0.6 ? '#DC2626' : val.ownership_opacity_score > 0.35 ? '#D97706' : '#16A34A' }} />
      </Field>
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const s = VERDICT_STYLE[verdict] || { bg: '#F4F6F8', color: '#757B86', label: verdict.toUpperCase() };
  return (
    <span style={{ background: s.bg, color: s.color, border: `1px solid ${s.color}30`, borderRadius: 5, padding: '3px 8px', font: "700 10px 'JetBrains Mono'" }}>
      {s.label}
    </span>
  );
}

function FatfBadge({ status }: { status: string }) {
  const s = FATF_STYLE[status] || { bg: '#F4F6F8', color: '#757B86' };
  return (
    <span style={{ background: s.bg, color: s.color, borderRadius: 4, padding: '2px 6px', font: "600 9px 'JetBrains Mono'" }}>
      FATF {status.toUpperCase()}
    </span>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export interface ChallengeReviewPanelProps {
  paymentId: string;
  onClose: () => void;
  onChallengeOpened?: (challengeId: string) => void;
  onChallengeResponded?: (challengeId: string) => void;
}

export function ChallengeReviewPanel({
  paymentId,
  onClose,
  onChallengeOpened,
  onChallengeResponded,
}: ChallengeReviewPanelProps) {
  const [step, setStep] = useState<Step>('form');
  const [form, setForm] = useState<FormState>(() => ({ ...initialForm(), transaction_id: paymentId }));
  const [caseId, setCaseId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [similarCases, setSimilarCases] = useState<SimilarCase[]>([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);

  // Challenge modal state
  const [activeSimilar, setActiveSimilar] = useState<SimilarCase | null>(null);
  const [challengeResult, setChallengeResult] = useState<ChallengeResult | null>(null);
  const [generatingChallenge, setGeneratingChallenge] = useState(false);
  const [challengeError, setChallengeError] = useState<string | null>(null);
  const [responseText, setResponseText] = useState('');
  const [submittingResponse, setSubmittingResponse] = useState(false);
  const [responseSubmitted, setResponseSubmitted] = useState(false);
  const [demoRunning, setDemoRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (generatingChallenge) {
      setElapsed(0);
      elapsedRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
    } else {
      if (elapsedRef.current) clearInterval(elapsedRef.current);
      setElapsed(0);
    }
    return () => { if (elapsedRef.current) clearInterval(elapsedRef.current); };
  }, [generatingChallenge]);

  // Typewriter-style demo fill: reveal each field with a short delay so
  // the audience can see the form being "completed" before auto-submit.
  const runDemo = useCallback(async () => {
    setDemoRunning(true);
    const base = { ...DEMO_FORM, transaction_id: 'REVIEW-TXN-' + Date.now().toString(36).toUpperCase() };

    const delay = (ms: number) => new Promise(r => setTimeout(r, ms));

    setForm(f => ({ ...f, transaction_id: base.transaction_id })); await delay(600);
    setForm(f => ({ ...f, amount: base.amount, currency: base.currency })); await delay(600);
    setForm(f => ({ ...f, product_type: base.product_type, direction: base.direction, has_trade_context: true })); await delay(700);
    setForm(f => ({ ...f, originator: base.originator })); await delay(900);
    setForm(f => ({ ...f, beneficiary: base.beneficiary })); await delay(900);
    setForm(f => ({ ...f, goods_description: base.goods_description, hs_code: base.hs_code, dual_use_flag: true, invoice_amount: base.invoice_amount, shipment_country: base.shipment_country })); await delay(800);
    setForm(f => ({ ...f, relationship_tenure_days: base.relationship_tenure_days, first_transaction_to_counterparty: true, referral_origin: base.referral_origin })); await delay(700);
    setForm(f => ({ ...f, typology_tags: base.typology_tags, risk_scores: base.risk_scores, reviewer_verdict: base.reviewer_verdict, reviewer_rationale: base.reviewer_rationale })); await delay(900);

    // auto-submit
    setSubmitting(true);
    setSubmitError(null);
    try {
      const xml = buildXml(base);
      const { case_id } = await challengeApi.submit(base.transaction_id, xml);
      setCaseId(case_id);
      setLoadingSimilar(true);
      const similar = await challengeApi.findSimilar(case_id);
      setSimilarCases(similar);
      setStep('similar');
    } catch (e: any) {
      setSubmitError(e.message ?? 'Demo submission failed');
    } finally {
      setSubmitting(false);
      setLoadingSimilar(false);
      setDemoRunning(false);
    }
  }, []);

  // Derive geopolitical snapshot from current form
  const countries = [form.originator.country_of_incorporation, form.beneficiary.country_of_incorporation]
    .filter(Boolean).map(c => c.toUpperCase());
  const geoSnapshot = buildGeoSnapshot(countries);

  const setParty = (side: 'originator' | 'beneficiary') => (p: Party) =>
    setForm(f => ({ ...f, [side]: p }));

  const handleSubmit = useCallback(async () => {
    if (!form.transaction_id.trim()) {
      setSubmitError('Transaction ID is required');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const xml = buildXml(form);
      const { case_id } = await challengeApi.submit(form.transaction_id, xml);
      setCaseId(case_id);

      setLoadingSimilar(true);
      const similar = await challengeApi.findSimilar(case_id);
      setSimilarCases(similar);
      setStep('similar');
    } catch (e: any) {
      setSubmitError(e.message ?? 'Submission failed');
    } finally {
      setSubmitting(false);
      setLoadingSimilar(false);
    }
  }, [form]);

  const openChallenge = (sc: SimilarCase) => {
    setActiveSimilar(sc);
    setChallengeResult(null);
    setChallengeError(null);
    setResponseText('');
    setResponseSubmitted(false);
    setStep('challenge');
  };

  const handleGenerateChallenge = async () => {
    if (!caseId || !activeSimilar) return;
    setGeneratingChallenge(true);
    setChallengeError(null);
    try {
      const result = await challengeApi.generateChallenge(caseId, activeSimilar.case_id, form.reviewer_verdict);
      setChallengeResult(result);
      onChallengeOpened?.(result.challenge_id);
    } catch (e: any) {
      setChallengeError(e.message ?? 'Challenge generation failed');
    } finally {
      setGeneratingChallenge(false);
    }
  };

  const handleSubmitResponse = async () => {
    if (!caseId || !challengeResult) return;
    setSubmittingResponse(true);
    try {
      await challengeApi.respond(caseId, challengeResult.challenge_id, responseText);
      onChallengeResponded?.(challengeResult.challenge_id);
      setResponseSubmitted(true);
    } catch (e: any) {
      setChallengeError(e.message ?? 'Failed to submit response');
    } finally {
      setSubmittingResponse(false);
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'rgba(14,17,22,0.45)', zIndex: 199, backdropFilter: 'blur(2px)' }}
      />

      {/* Drawer */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: 500,
        zIndex: 200, display: 'flex', flexDirection: 'column',
        background: '#fff', boxShadow: '-8px 0 40px rgba(14,17,22,0.18)',
        borderLeft: '1px solid #E1E4E9',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 18px', borderBottom: '1px solid #EEF0F3', flex: '0 0 auto' }}>
          <div>
            <div style={{ font: "700 14px 'Hanken Grotesk'", color: '#14171C' }}>Challenge Review</div>
            <div style={{ font: "500 11px 'JetBrains Mono'", color: '#9AA0AA', marginTop: 2 }}>
              {step === 'form' ? 'Step 1 — Case form' : step === 'similar' ? 'Step 2 — Similar cases' : 'Step 3 — Challenge'}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {step !== 'form' && (
              <button
                onClick={() => setStep(step === 'challenge' ? 'similar' : 'form')}
                style={{ font: "500 12px 'Hanken Grotesk'", color: '#757B86', background: 'none', border: '1px solid #E1E4E9', borderRadius: 7, padding: '6px 12px', cursor: 'pointer' }}
              >
                ← Back
              </button>
            )}
            <button onClick={onClose} style={{ background: '#F4F6F8', border: 'none', borderRadius: 7, width: 30, height: 30, cursor: 'pointer', font: '700 14px sans-serif', color: '#757B86', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>×</button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: '1 1 auto', overflow: 'auto', padding: '16px 18px' }}>

          {/* ── STEP 1: Form ─────────────────────────────────────────────── */}
          {step === 'form' && (
            <div>
              {/* Demo button */}
              <button
                onClick={runDemo}
                disabled={demoRunning || submitting}
                style={{
                  width: '100%', marginBottom: 14,
                  background: demoRunning || submitting ? '#F4F6F8' : 'linear-gradient(135deg,#1a1f28 0%,#2C7BE5 100%)',
                  color: demoRunning || submitting ? '#9AA0AA' : '#fff',
                  border: 'none', borderRadius: 10, padding: '12px 18px',
                  font: "700 13px 'Hanken Grotesk'", cursor: demoRunning || submitting ? 'default' : 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  boxShadow: demoRunning || submitting ? 'none' : '0 4px 14px rgba(44,123,229,0.35)',
                  transition: 'all .15s',
                }}
              >
                {demoRunning ? (
                  <>
                    <span style={{ display: 'inline-block', width: 14, height: 14, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#9AA0AA', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
                    Filling demo case…
                  </>
                ) : submitting ? (
                  <>
                    <span style={{ display: 'inline-block', width: 14, height: 14, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#9AA0AA', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
                    Finding similar cases…
                  </>
                ) : (
                  <>⚡ Auto-fill &amp; Run Demo</>
                )}
              </button>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <div style={{ flex: 1, height: 1, background: '#EEF0F3' }} />
                <span style={{ font: "500 10px 'Hanken Grotesk'", color: '#B4BAC2' }}>or fill manually</span>
                <div style={{ flex: 1, height: 1, background: '#EEF0F3' }} />
              </div>
              <SectionHeader title="Transaction Details" />
              <div style={{ background: '#F7F8FA', border: '1px solid #EEF0F3', borderRadius: 9, padding: '12px 13px', marginBottom: 12 }}>
                <Field label="Transaction ID">
                  <input style={inp} value={form.transaction_id} onChange={e => setForm(f => ({ ...f, transaction_id: e.target.value }))} />
                </Field>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px 1fr', gap: 8 }}>
                  <Field label="Amount">
                    <input style={inp} type="number" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} />
                  </Field>
                  <Field label="Currency">
                    <input style={inp} value={form.currency} onChange={e => setForm(f => ({ ...f, currency: e.target.value }))} maxLength={10} />
                  </Field>
                  <Field label="Value date">
                    <input style={inp} type="date" value={form.value_date} onChange={e => setForm(f => ({ ...f, value_date: e.target.value }))} />
                  </Field>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <Field label="Product type">
                    <select style={sel} value={form.product_type} onChange={e => setForm(f => ({ ...f, product_type: e.target.value, has_trade_context: e.target.value === 'trade_finance' }))}>
                      <option value="wire_transfer">Wire Transfer</option>
                      <option value="trade_finance">Trade Finance</option>
                      <option value="crypto">Crypto</option>
                    </select>
                  </Field>
                  <Field label="Direction">
                    <select style={sel} value={form.direction} onChange={e => setForm(f => ({ ...f, direction: e.target.value }))}>
                      <option value="outbound">Outbound</option>
                      <option value="inbound">Inbound</option>
                    </select>
                  </Field>
                </div>
              </div>

              <SectionHeader title="Originator" />
              <PartySection label="Originator" val={form.originator} onChange={setParty('originator')} />

              <SectionHeader title="Beneficiary" />
              <PartySection label="Beneficiary" val={form.beneficiary} onChange={setParty('beneficiary')} />

              {/* Trade Context — collapsible, only for trade_finance */}
              {form.product_type === 'trade_finance' && (
                <>
                  <SectionHeader title="Trade Context" />
                  <div style={{ background: '#F7F8FA', border: '1px solid #EEF0F3', borderRadius: 9, padding: '12px 13px', marginBottom: 12 }}>
                    <Field label="Goods description">
                      <input style={inp} value={form.goods_description} onChange={e => setForm(f => ({ ...f, goods_description: e.target.value }))} />
                    </Field>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      <Field label="HS code">
                        <input style={inp} value={form.hs_code} onChange={e => setForm(f => ({ ...f, hs_code: e.target.value }))} placeholder="e.g. 8412.21" />
                      </Field>
                      <Field label="Shipment country">
                        <input style={inp} value={form.shipment_country} onChange={e => setForm(f => ({ ...f, shipment_country: e.target.value }))} maxLength={2} />
                      </Field>
                    </div>
                    <Field label="Invoice amount">
                      <input style={inp} type="number" value={form.invoice_amount} onChange={e => setForm(f => ({ ...f, invoice_amount: e.target.value }))} />
                    </Field>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, font: "500 12px 'Hanken Grotesk'", color: '#41464F', cursor: 'pointer', marginTop: 4 }}>
                      <input type="checkbox" checked={form.dual_use_flag} onChange={e => setForm(f => ({ ...f, dual_use_flag: e.target.checked }))} />
                      <span>Dual-use flag</span>
                      <span style={{ font: "500 10px 'JetBrains Mono'", color: '#D97706' }}>⚠ triggers Wassenaar check</span>
                    </label>
                  </div>
                </>
              )}

              <SectionHeader title="Relationship Context" />
              <div style={{ background: '#F7F8FA', border: '1px solid #EEF0F3', borderRadius: 9, padding: '12px 13px', marginBottom: 12 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <Field label="Relationship tenure (days)">
                    <input style={inp} type="number" value={form.relationship_tenure_days} onChange={e => setForm(f => ({ ...f, relationship_tenure_days: e.target.value }))} />
                  </Field>
                  <Field label="Referral origin">
                    <select style={sel} value={form.referral_origin} onChange={e => setForm(f => ({ ...f, referral_origin: e.target.value }))}>
                      <option value="cold_contact">Cold Contact</option>
                      <option value="existing_relationship">Existing Relationship</option>
                      <option value="platform">Platform</option>
                      <option value="unknown">Unknown</option>
                    </select>
                  </Field>
                </div>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, font: "500 12px 'Hanken Grotesk'", color: '#41464F', cursor: 'pointer', marginTop: 4 }}>
                  <input type="checkbox" checked={form.first_transaction_to_counterparty} onChange={e => setForm(f => ({ ...f, first_transaction_to_counterparty: e.target.checked }))} />
                  First transaction to this counterparty
                </label>
              </div>

              <SectionHeader title="Analyst Assessment" />
              <div style={{ background: '#F7F8FA', border: '1px solid #EEF0F3', borderRadius: 9, padding: '12px 13px', marginBottom: 12 }}>
                <Field label="Typology tags">
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {TYPOLOGY_TAGS.map(tag => {
                      const active = form.typology_tags.includes(tag);
                      return (
                        <button key={tag}
                          onClick={() => setForm(f => ({
                            ...f,
                            typology_tags: active ? f.typology_tags.filter(t => t !== tag) : [...f.typology_tags, tag],
                          }))}
                          style={{
                            background: active ? '#14171C' : '#fff', color: active ? '#fff' : '#757B86',
                            border: `1px solid ${active ? '#14171C' : '#E1E4E9'}`, borderRadius: 6,
                            padding: '5px 10px', font: "600 11px 'Hanken Grotesk'", cursor: 'pointer',
                          }}>
                          {tag}
                        </button>
                      );
                    })}
                  </div>
                </Field>

                <div style={{ marginTop: 8 }}>
                  {(['source_of_wealth', 'document_consistency', 'counterparty_opacity', 'relationship_novelty'] as const).map(key => (
                    <Field key={key} label={`${key.replace(/_/g, ' ')} — ${form.risk_scores[key].toFixed(1)}/10`}>
                      <input type="range" min={0} max={10} step={0.5} value={form.risk_scores[key]}
                        onChange={e => setForm(f => ({ ...f, risk_scores: { ...f.risk_scores, [key]: parseFloat(e.target.value) } }))}
                        style={{ width: '100%', accentColor: form.risk_scores[key] > 7 ? '#DC2626' : form.risk_scores[key] > 5 ? '#D97706' : '#16A34A' }} />
                    </Field>
                  ))}
                </div>

                <Field label="Draft verdict">
                  <select style={sel} value={form.reviewer_verdict} onChange={e => setForm(f => ({ ...f, reviewer_verdict: e.target.value }))}>
                    <option value="approved">Approved</option>
                    <option value="blocked">Blocked</option>
                    <option value="escalated">Escalated</option>
                  </select>
                </Field>

                <Field label="Reviewer rationale">
                  <textarea
                    style={{ ...inp, minHeight: 80, resize: 'vertical' }}
                    value={form.reviewer_rationale}
                    onChange={e => setForm(f => ({ ...f, reviewer_rationale: e.target.value }))}
                    placeholder="Document your reasoning…"
                  />
                </Field>
              </div>

              {/* Geopolitical context — read-only, auto-populated */}
              <SectionHeader title="Geopolitical Context (auto-populated · read-only)" />
              <div style={{ background: '#F7F8FA', border: '1px solid #EEF0F3', borderRadius: 9, padding: '12px 13px', marginBottom: 12 }}>
                <div style={{ font: "500 10px 'JetBrains Mono'", color: '#9AA0AA', marginBottom: 8 }}>
                  Snapshot captured at review time from live feeds (FATF, Basel AML Index, OFAC, BIS).
                </div>
                {Object.entries(geoSnapshot).length === 0 && (
                  <div style={{ font: "500 11px 'Hanken Grotesk'", color: '#B4BAC2' }}>
                    Enter originator / beneficiary countries to populate.
                  </div>
                )}
                {Object.entries(geoSnapshot).map(([cc, ctx]) => (
                  <div key={cc} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 8, padding: '8px 10px', background: '#fff', borderRadius: 7, border: '1px solid #EEF0F3' }}>
                    <div style={{ font: "700 13px 'JetBrains Mono'", color: '#14171C', minWidth: 28 }}>{cc}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        <FatfBadge status={ctx.FATF_status} />
                        <span style={{ font: "500 10px 'JetBrains Mono'", color: '#757B86' }}>Basel {ctx.basel_aml_index_score}</span>
                      </div>
                      {ctx.active_sanctions_programs.length > 0 && (
                        <div style={{ font: "500 10px 'JetBrains Mono'", color: '#DC2626', marginTop: 4 }}>
                          {ctx.active_sanctions_programs.join(' · ')}
                        </div>
                      )}
                      {ctx.export_control_alerts.length > 0 && (
                        <div style={{ font: "500 10px 'JetBrains Mono'", color: '#D97706', marginTop: 2 }}>
                          {ctx.export_control_alerts.join(' · ')}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {submitError && (
                <div style={{ background: '#FCEBEB', border: '1px solid #F3C9C9', borderRadius: 8, padding: '10px 13px', marginBottom: 12, font: "500 12px 'Hanken Grotesk'", color: '#DC2626' }}>
                  {submitError}
                </div>
              )}
            </div>
          )}

          {/* ── STEP 2: Similar cases ────────────────────────────────────── */}
          {step === 'similar' && (
            <div>
              {loadingSimilar && (
                <div style={{ textAlign: 'center', padding: 40, font: "500 13px 'Hanken Grotesk'", color: '#9AA0AA' }}>
                  Finding similar cases…
                </div>
              )}
              {!loadingSimilar && similarCases.length === 0 && (
                <div style={{ textAlign: 'center', padding: 40, font: "500 13px 'Hanken Grotesk'", color: '#9AA0AA' }}>
                  No similar cases found. The dataset may still be building.
                </div>
              )}
              {!loadingSimilar && similarCases.map(sc => {
                const vs = VERDICT_STYLE[sc.reviewer_verdict] ?? { bg: '#F4F6F8', color: '#757B86', label: sc.reviewer_verdict.toUpperCase() };
                const pct = Math.round(sc.similarity_score * 100);
                return (
                  <div key={sc.case_id} style={{ background: '#fff', border: `1.5px solid ${sc.contradicts_current ? '#F3C9C9' : '#EEF0F3'}`, borderRadius: 10, padding: '13px 14px', marginBottom: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ font: "700 20px 'JetBrains Mono'", color: pct >= 70 ? '#14171C' : '#9AA0AA' }}>{pct}%</div>
                        <div style={{ font: "500 10px 'Hanken Grotesk'", color: '#9AA0AA' }}>match</div>
                      </div>
                      <VerdictBadge verdict={sc.reviewer_verdict} />
                    </div>

                    <div style={{ font: "600 12px 'Hanken Grotesk'", color: '#14171C', marginBottom: 4 }}>
                      {sc.summary.entity_names?.join(' → ')}
                    </div>
                    <div style={{ font: "500 11px 'JetBrains Mono'", color: '#757B86', marginBottom: 6 }}>
                      {sc.summary.amount?.toLocaleString()} {sc.summary.currency} · {sc.transaction_id}
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 8 }}>
                      {(sc.summary.typology_tags || []).map(t => (
                        <span key={t} style={{ background: '#F4F6F8', color: '#41464F', border: '1px solid #E1E4E9', borderRadius: 4, padding: '2px 7px', font: "500 10px 'JetBrains Mono'" }}>{t}</span>
                      ))}
                    </div>

                    {/* Geopolitical context snapshot date */}
                    {sc.review_timestamp && (
                      <div style={{ font: "500 10px 'JetBrains Mono'", color: '#B4BAC2', marginBottom: 8 }}>
                        Geo snapshot: {sc.review_timestamp.slice(0, 10)}
                      </div>
                    )}

                    {sc.contradicts_current && (
                      <button
                        onClick={() => openChallenge(sc)}
                        style={{ width: '100%', background: '#FCEBEB', color: '#DC2626', border: '1.5px solid #F3C9C9', borderRadius: 8, padding: '9px 14px', font: "700 12px 'Hanken Grotesk'", cursor: 'pointer', marginTop: 4 }}>
                        ⚡ This contradicts my draft verdict — open challenge
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* ── STEP 3: Challenge modal contents ────────────────────────── */}
          {step === 'challenge' && activeSimilar && (
            <div>
              {/* Side-by-side summary */}
              <SectionHeader title="Case Comparison" />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                {[
                  { label: 'Current case', txn: form.transaction_id, amount: form.amount, currency: form.currency, tags: form.typology_tags, verdict: form.reviewer_verdict, risk: form.risk_scores, geo: geoSnapshot },
                  { label: 'Precedent case', txn: activeSimilar.transaction_id, amount: String(activeSimilar.summary.amount), currency: activeSimilar.summary.currency, tags: activeSimilar.summary.typology_tags, verdict: activeSimilar.reviewer_verdict, risk: activeSimilar.summary.risk_scores, geo: activeSimilar.geopolitical_snapshot },
                ].map(c => (
                  <div key={c.label} style={{ background: '#F7F8FA', border: '1px solid #EEF0F3', borderRadius: 9, padding: '10px 12px' }}>
                    <div style={{ font: "700 10px 'Hanken Grotesk'", color: '#9AA0AA', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 6 }}>{c.label}</div>
                    <div style={{ font: "600 12px 'Hanken Grotesk'", color: '#14171C' }}>{c.txn}</div>
                    <div style={{ font: "500 11px 'JetBrains Mono'", color: '#757B86', margin: '3px 0 6px' }}>
                      {Number(c.amount).toLocaleString()} {c.currency}
                    </div>
                    <VerdictBadge verdict={c.verdict} />
                    <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {c.tags.map(t => <span key={t} style={{ background: '#ECEEF1', color: '#41464F', borderRadius: 3, padding: '1px 5px', font: "500 9px 'JetBrains Mono'" }}>{t}</span>)}
                    </div>
                    {c.risk && (
                      <div style={{ marginTop: 8 }}>
                        {Object.entries(c.risk).slice(0, 4).map(([k, v]) => (
                          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', font: "500 10px 'JetBrains Mono'", color: '#757B86', marginBottom: 2 }}>
                            <span>{k.slice(0, 12)}</span>
                            <span style={{ color: Number(v) > 7 ? '#DC2626' : Number(v) > 5 ? '#D97706' : '#16A34A', fontWeight: 700 }}>{Number(v).toFixed(1)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {Object.entries(c.geo).slice(0, 2).map(([cc, ctx]) => (
                      <div key={cc} style={{ marginTop: 6 }}>
                        <FatfBadge status={(ctx as GeoContext).FATF_status} />
                        {' '}<span style={{ font: "500 9px 'JetBrains Mono'", color: '#9AA0AA' }}>{cc}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>

              {/* Challenge generation */}
              {!challengeResult && !generatingChallenge && (
                <button
                  onClick={handleGenerateChallenge}
                  style={{ width: '100%', background: '#14171C', color: '#fff', border: 'none', borderRadius: 9, padding: '12px 18px', font: "700 13px 'Hanken Grotesk'", cursor: 'pointer', marginBottom: 12 }}>
                  Generate Challenge
                </button>
              )}

              {generatingChallenge && (
                <div style={{ background: '#F7F8FA', border: '1px solid #EEF0F3', borderRadius: 10, padding: '20px 16px', marginBottom: 12, textAlign: 'center' }}>
                  <div style={{ display: 'inline-block', width: 22, height: 22, border: '2.5px solid #E1E4E9', borderTopColor: '#14171C', borderRadius: '50%', animation: 'spin 0.7s linear infinite', marginBottom: 12 }} />
                  <div style={{ font: "700 13px 'Hanken Grotesk'", color: '#14171C', marginBottom: 4 }}>Ollama is analysing the tension…</div>
                  <div style={{ font: "500 12px 'JetBrains Mono'", color: '#9AA0AA', marginBottom: 10 }}>{elapsed}s elapsed · typically 15–25s</div>
                  <div style={{ height: 4, background: '#E1E4E9', borderRadius: 4, overflow: 'hidden' }}>
                    <div style={{ height: '100%', background: 'linear-gradient(90deg,#2C7BE5,#14171C)', borderRadius: 4, width: `${Math.min((elapsed / 25) * 100, 95)}%`, transition: 'width 1s linear' }} />
                  </div>
                </div>
              )}

              {challengeError && (
                <div style={{ background: '#FCEBEB', border: '1px solid #F3C9C9', borderRadius: 8, padding: 12, marginBottom: 12, font: "500 12px 'Hanken Grotesk'", color: '#DC2626' }}>
                  {challengeError}
                </div>
              )}

              {challengeResult && (
                <>
                  {/* LLM challenge text */}
                  <blockquote style={{ background: '#F7F8FA', borderLeft: '3px solid #14171C', margin: '0 0 14px', padding: '14px 16px', borderRadius: '0 9px 9px 0', font: "500 12.5px/1.7 'Hanken Grotesk'", color: '#14171C' }}>
                    {challengeResult.challenge_text}
                  </blockquote>

                  {!responseSubmitted ? (
                    <>
                      <div style={{ font: "700 11px 'Hanken Grotesk'", color: '#757B86', marginBottom: 6 }}>
                        Your response to this challenge
                      </div>
                      <textarea
                        style={{ ...inp, minHeight: 80, resize: 'vertical', marginBottom: 10 }}
                        value={responseText}
                        onChange={e => setResponseText(e.target.value)}
                        placeholder="Document how you distinguish this case from the precedent, or acknowledge the tension and explain your final reasoning…"
                      />
                      <button
                        onClick={handleSubmitResponse}
                        disabled={submittingResponse || !responseText.trim()}
                        style={{ width: '100%', background: submittingResponse || !responseText.trim() ? '#E1E4E9' : '#16A34A', color: '#fff', border: 'none', borderRadius: 9, padding: '11px 18px', font: "700 13px 'Hanken Grotesk'", cursor: submittingResponse || !responseText.trim() ? 'default' : 'pointer' }}>
                        {submittingResponse ? 'Submitting…' : 'Submit Response & Continue'}
                      </button>
                    </>
                  ) : (
                    <div style={{ background: '#E9F6EE', border: '1px solid #BFE4CC', borderRadius: 9, padding: 14, textAlign: 'center', font: "700 13px 'Hanken Grotesk'", color: '#16A34A' }}>
                      ✓ Response recorded. You may now proceed to your verdict.
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer CTA */}
        {step === 'form' && (
          <div style={{ flex: '0 0 auto', borderTop: '1px solid #EEF0F3', padding: '14px 18px' }}>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              style={{ width: '100%', background: submitting ? '#E1E4E9' : '#14171C', color: '#fff', border: 'none', borderRadius: 9, padding: '13px 18px', font: "700 13px 'Hanken Grotesk'", cursor: submitting ? 'default' : 'pointer' }}>
              {submitting ? 'Saving…' : 'Save & Find Similar Cases →'}
            </button>
          </div>
        )}
      </div>

      {/* Spin animation */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}
