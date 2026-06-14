export interface Factor {
  name: string; score: number; weight: number; detail: string;
  sub?: { l: string; s: number; d: string }[];
}
export interface NetworkNode {
  id: string; label: string; sub: string; hop: number; taint: number;
  isSdn: boolean; shared: string; contrib: number; marginal: number;
}
export interface ChainLink { label: string; sub: string; pct: string | null; sdn: boolean; }
export interface ClusterNode { label: string; sub: string; subject: boolean; }
export interface Network {
  type: 'noisyor' | 'ownership' | 'cluster';
  id: string;
  risk?: number;
  formula?: string;
  nodes?: NetworkNode[];
  chain?: ChainLink[];
  effective?: string;
  cluster?: ClusterNode[];
  shadow?: string;
}
export interface PayTag { k: string; label: string; note: string; }
export interface Pay {
  amount: string; amountSub: string; corridor: string; rail: string;
  senderName: string; senderWallet: string; senderUbo: string;
  receiverName: string; receiverWallet: string; receiverUbo: string;
  tags: PayTag[];
}
export interface Profile {
  regNo: string; incorporated: string; jurisdiction: string; structure: string;
  uboStatus: string; uboDepth: string; uboName: string; uboDetail: string;
  kybStatus: string; kybAddress: string;
  corpFlags: string[];
  adverse: { src: string; date: string; rel: number }[];
  histScreen: number; histHits: number; histRate: string;
}
export interface Case {
  id: string; entity: string; entityType: string;
  verdict: 'MATCH' | 'REVIEW' | 'NO_MATCH';
  track: string; trackLong: string; threshold: number;
  country: string; tier: string; transfer: string; lists: string; slaMins: number;
  flags: string[];
  causeHead: string; causeBody: string;
  composite?: number;
  pay: Pay;
  factors?: Factor[];
  noFactorsHead?: string; noFactorsBody?: string;
  network: Network | null;
  profile: Profile;
  audit: string;
}

export const DEMO_CASES: Case[] = [
  {
    id: 'ENT-20240613-8821', entity: 'Al-Qadir Trading LLC', entityType: 'business (KYB)',
    verdict: 'REVIEW', track: 'B:risk', trackLong: 'Track B — risk-score escalation', threshold: 0.50,
    country: 'United Arab Emirates', tier: 'GREY', transfer: 'Inbound', lists: 'EU Consolidated', slaMins: 47,
    flags: ['MiCA', 'TRON·EU'],
    causeHead: 'REVIEW — routed to a human, not blocked',
    causeBody: "No sanctions-list MATCH; Track A is clean. The case is escalated by the Track B risk score (R ≥ 0.50). Network association raises suspicion but, by design, can only route to REVIEW — never an autonomous block. Top drivers: an identity-alias signal against the EU Consolidated List (mirrored as a feature only), entity-profile risk (UAE grey-list ×1.35, agent address, 8-month-old entity, secondary UBO unresolved), and noisy-OR network exposure 0.575 one hop from a confirmed OFAC SDN.",
    pay: { amount: '48,200 USDT', amountSub: '≈ $48,200', corridor: 'AE → AE', rail: 'TRON · USDT', senderName: 'Crescent Hawala Exchange', senderWallet: 'TXk9f2…b7Qd2', senderUbo: 'EXTERNAL', receiverName: 'Al-Qadir Trading LLC', receiverWallet: 'TR8mP4…r1Lp4', receiverUbo: 'PARTIAL', tags: [{ k: 'MiCA', label: 'MiCA_COMPLIANCE_RISK', note: 'USDT is not MiCA-authorised (mid-2026); EU-linked corridor → legal review, not a score change.' }, { k: 'TRON', label: 'TRON_EU_CORRIDOR_REVIEW', note: 'TRON/USDT settlement on a EU/UK-touching corridor — informational policy flag.' }] },
    factors: [
      { name: 'Identity match signal', score: 0.71, weight: 0.25, detail: "Name 'Al-Qadir Trading LLC' matches alias 'Al Qadir Trade (LLC)' on the EU Consolidated List (entry EU-2023-0084-ENTITY) at 71% — phonetic + edit-distance 3. Mirrored from Track A as a feature only; the list adjudication itself lives in Track A.", sub: [{ l: 'OFAC SDN', s: 0.12, d: 'No match' }, { l: 'EU Consolidated', s: 0.71, d: 'EU-2023-0084-ENTITY' }, { l: 'UN List', s: 0.05, d: 'No significant match' }] },
      { name: 'Behavioral / txn anomaly', score: 0.60, weight: 0.20, detail: 'Velocity 2.1× the entity baseline over 30 days; 4 transfers clustered just below the $10,000 CTR threshold — structuring. Amount z-score 2.8 vs own history.' },
      { name: 'Network / graph exposure', score: 0.575, weight: 0.20, detail: 'noisy-OR 0.575: 1 hop from a confirmed OFAC SDN (p=1.0, λ¹ → 0.50) and 2 hops from REVIEW entity ENT-8820 (p=0.6, λ² → 0.15). Leave-one-out attribution in the network panel. Routed to REVIEW — not blocked on association alone.' },
      { name: 'Entity risk profile', score: 0.80, weight: 0.15, detail: 'UAE (FATF grey-list, ×1.35 multiplier applied within this sub-score). Secondary UBO unresolved at depth 3 → PARTIAL. Registered at agent address; incorporated 8 months ago; 2 adverse-media articles.' },
      { name: 'Document / onboarding integrity', score: 0.60, weight: 0.10, detail: 'Certificate of incorporation unverifiable against the UAE registry; registered address differs from stated operating address.' },
      { name: 'Historical flag rate', score: 0.46, weight: 0.10, detail: 'Beta(1,9)-smoothed prior flag rate 0.046 over 40 screenings; 1 prior confirmed-true hit. No upward adjustment to a Track A verdict.' },
    ],
    network: { type: 'noisyor', id: 'NET-2024-0071', risk: 0.575, formula: '1 − (1 − 1.0×0.5¹)(1 − 0.6×0.5²) = 1 − (0.50)(0.85) = 0.575', nodes: [{ id: 'ENT-8820', label: 'Zarobi Holdings', sub: 'REVIEW · ENT-8820', hop: 2, taint: 0.6, isSdn: false, shared: 'director_id', contrib: 0.15, marginal: 0.075 }, { id: 'SDN-OFAC', label: 'OFAC SDN address', sub: 'confirmed · TXr3…9F2a', hop: 1, taint: 1.0, isSdn: true, shared: 'registered_address', contrib: 0.50, marginal: 0.425 }, { id: 'ENT-20240613-8821', label: 'Al-Qadir Trading LLC', sub: 'subject', hop: 0, taint: 0.64, isSdn: false, shared: '', contrib: 0, marginal: 0 }] },
    profile: { regNo: 'UAE-DMCC-194872', incorporated: '2025-10', jurisdiction: 'UAE · DMCC', structure: 'Free-zone LLC', uboStatus: 'PARTIAL', uboDepth: '2 of ≥3', uboName: 'Ahmad Khalid Mansour', uboDetail: 'Primary UBO verified & screened (clean). Secondary UBO unresolved at depth 3 → PARTIAL: account active under enhanced monitoring, every transaction screened.', kybStatus: 'PARTIAL', kybAddress: 'TR8mP4…r1Lp4', corpFlags: ['registered_agent_address', 'age_under_6_months'], adverse: [{ src: 'Reuters', date: '2024-03-12', rel: 0.67 }, { src: 'Al Arabiya', date: '2022-11-05', rel: 0.44 }], histScreen: 40, histHits: 1, histRate: '0.046' },
    audit: "REVIEW — composite risk 0.64 (threshold 0.50). No sanctions-list MATCH; routed to human review by Track B. Identity: 'Al-Qadir Trading LLC' ↔ EU Consolidated alias 'Al Qadir Trade (LLC)' (EU-2023-0084-ENTITY), phonetic+edit-distance, 71% — feature only. Network: noisy-OR 0.575, 1 hop from confirmed OFAC SDN address (marginal 0.425), 2 hops from REVIEW entity ENT-8820 (marginal 0.075); routed to REVIEW, not blocked on association alone. Entity profile: UAE FATF grey-list (×1.35), incorporated 8 months ago, registered at agent address, secondary UBO unresolved at depth 3 (PARTIAL). Behavioral: 4 transfers below the $10,000 CTR threshold, velocity z-score 2.8. List versions in force: OFAC 2026-06-12, EU 2026-06-11. Algorithm v1.1.",
  },
  {
    id: 'ENT-20240613-7740', entity: 'Thames Import Solutions Ltd', entityType: 'business (KYB)',
    verdict: 'MATCH', track: 'A:50pct-rule', trackLong: 'Track A — OFAC 50% Rule (deterministic)', threshold: 0.50,
    country: 'United Kingdom', tier: 'STANDARD', transfer: 'Outbound', lists: 'OFAC SDN', slaMins: 11, flags: [],
    causeHead: 'MATCH — payment blocked · 50% Rule',
    causeBody: 'The beneficiary is owned ≥50% in aggregate by a named OFAC SDN through an established ownership chain. This is a deterministic legal block under the OFAC 50% Rule — not a risk inference — so the risk score is irrelevant. All chain percentages are confirmed (UK PSC + OpenCorporates).',
    pay: { amount: '$220,000', amountSub: 'SWIFT · USD', corridor: 'GB → BVI', rail: 'SWIFT', senderName: 'Thames Import Solutions Ltd', senderWallet: 'GB-CRN 09913442', senderUbo: 'FULL', receiverName: 'Meridian Global Ltd', receiverWallet: 'BVI-1804772', receiverUbo: 'UNRESOLVED', tags: [] },
    noFactorsHead: 'Risk score not used for this verdict', noFactorsBody: 'MATCH is decided in Track A by the deterministic 50% ownership rule. The Track B waterfall can only add suspicion (escalate to REVIEW); it can never participate in a block.',
    network: { type: 'ownership', id: 'OWN-2024-0044', chain: [{ label: 'Thames Import Solutions Ltd', sub: 'UK Ltd · beneficiary', pct: null, sdn: false }, { label: 'Aldgate Finance Services', sub: 'Cyprus SPV', pct: '100%', sdn: false }, { label: 'Meridian Global Ltd', sub: 'BVI holding', pct: '60%', sdn: false }, { label: 'Ivan Petrov', sub: 'OFAC SDN · person', pct: '100%', sdn: true }], effective: '60% effective ownership by named SDN · ≥50% → deterministic block' },
    profile: { regNo: 'GB-09913442', incorporated: '2019-04', jurisdiction: 'United Kingdom', structure: 'UK → Cyprus → BVI', uboStatus: 'FULL', uboDepth: '3 of 3', uboName: 'Ivan Petrov (OFAC SDN)', uboDetail: 'Ownership chain fully established. Beneficial owner is a named OFAC SDN. 50% Rule satisfied at 60% aggregate ownership.', kybStatus: 'FULL', kybAddress: '—', corpFlags: ['bvi_cayman_offshore', 'dissolved_entity_in_chain'], adverse: [], histScreen: 7, histHits: 0, histRate: '0.10' },
    audit: "MATCH — BLOCKED. Beneficiary 'Meridian Global Ltd' owned 60% in aggregate by named OFAC SDN 'Ivan Petrov' via chain Thames Import Solutions Ltd → Aldgate Finance Services → Meridian Global Ltd → [SDN]. Ownership established; all chain percentages confirmed from UK PSC + OpenCorporates. OFAC 50% Rule (Track A:50pct-rule) — deterministic legal block, risk score irrelevant. List version in force: OFAC 2026-06-12. Algorithm v1.1.",
  },
  {
    id: 'ENT-20240613-7702', entity: 'Pars Tejarat Co.', entityType: 'business (KYB)',
    verdict: 'MATCH', track: 'A:country-sanctions', trackLong: 'Track A — comprehensive-sanctions jurisdiction', threshold: 0.50,
    country: 'Iran', tier: 'BLACK', transfer: 'Outbound', lists: 'OFAC Iran NSRP', slaMins: 4, flags: [],
    causeHead: 'MATCH — payment blocked · country sanctions',
    causeBody: 'The payment corridor involves Iran — subject to comprehensive OFAC / OFSI / EU countermeasures (BLACK tier). This is a deterministic legal prohibition encoded in the regulatory engine, not a score threshold. Legal basis: OFAC Iran NSRP program. Score irrelevant.',
    pay: { amount: '$96,500', amountSub: 'SWIFT · USD', corridor: 'AE → IR', rail: 'SWIFT', senderName: 'Helios Maritime DMCC', senderWallet: 'AE-DMCC-201144', senderUbo: 'FULL', receiverName: 'Pars Tejarat Co.', receiverWallet: 'IR-RC-88401', receiverUbo: 'N/A', tags: [{ k: 'BLACK', label: 'BLACK-TIER JURISDICTION', note: 'Comprehensive sanctions — Track A:country-sanctions legal block.' }] },
    noFactorsHead: 'Risk score not used for this verdict', noFactorsBody: 'MATCH is a deterministic legal block at the regulatory layer (comprehensive-sanctions jurisdiction). The Track B risk score does not participate.',
    network: null,
    profile: { regNo: 'IR-RC-88401', incorporated: '2014-02', jurisdiction: 'Iran', structure: 'Iranian trading co.', uboStatus: 'N/A', uboDepth: '—', uboName: '—', uboDetail: 'Resolution not performed — the corridor is a deterministic legal block at the regulatory layer.', kybStatus: 'EXTERNAL', kybAddress: '—', corpFlags: [], adverse: [], histScreen: 0, histHits: 0, histRate: '—' },
    audit: "MATCH — BLOCKED. Payment corridor involves Iran — comprehensive OFAC/OFSI/EU countermeasures (Track A:country-sanctions, BLACK tier). Legal basis: OFAC Iran NSRP program. Risk score irrelevant. List version in force: OFAC 2026-06-12. Algorithm v1.1.",
  },
  {
    id: 'ENT-20240613-8810', entity: 'Northgate Nominees Ltd', entityType: 'business (KYB)',
    verdict: 'REVIEW', track: 'A:partial', trackLong: 'Track A partial + mandatory UBO gate (§8.6)', threshold: 0.50,
    country: 'Seychelles', tier: 'OFFSHORE', transfer: 'Inbound', lists: '—', slaMins: 26, flags: ['UBO UNRESOLVED'],
    causeHead: 'REVIEW — UBO gate not cleared',
    causeBody: 'Beneficial ownership cannot be traced beyond the configured depth (4 hops). Under the KYB-only policy this triggers a mandatory REVIEW regardless of the numeric score (§8.6): an entity whose UBO cannot be established is treated equivalently to an anonymous counterparty. Activation is blocked until resolved to FULL or PARTIAL.',
    pay: { amount: '12,000 USDT', amountSub: '≈ $12,000', corridor: 'SC → GB', rail: 'TRON · USDT', senderName: 'Northgate Nominees Ltd', senderWallet: 'TLp7q…3aW1', senderUbo: 'UNRESOLVED', receiverName: 'Sterling Bridge Ltd', receiverWallet: 'TY2k8…8dC0', receiverUbo: 'FULL', tags: [{ k: 'UBO', label: 'UBO_UNRESOLVED', note: 'Wallet treated as external/anonymous for screening despite registry presence.' }] },
    noFactorsHead: 'Verdict driven by the UBO gate, not the waterfall', noFactorsBody: 'An UNRESOLVED UBO chain forces a mandatory REVIEW (§8.6) regardless of the numeric risk score. The waterfall is not the deciding factor here.',
    network: null,
    profile: { regNo: 'SC-IBC-771204', incorporated: '2025-12', jurisdiction: 'Seychelles (offshore)', structure: 'IBC + nominee director', uboStatus: 'UNRESOLVED', uboDepth: '>4 (unresolved)', uboName: '— cannot establish', uboDetail: 'Chain breaks at a nominee-director layer; no PSC filed; opaque beyond depth 4. +0.40 ubo_unresolved corporate-risk signal applied.', kybStatus: 'UNRESOLVED', kybAddress: 'TLp7q…3aW1', corpFlags: ['nominee_director', 'psc_missing', 'ubo_unresolved'], adverse: [], histScreen: 3, histHits: 0, histRate: '0.10' },
    audit: "REVIEW — UBO chain UNRESOLVED beyond depth 4 (§8.6 mandatory gate). Entity treated as anonymous counterparty; activation blocked pending resolution to FULL/PARTIAL. Offshore jurisdiction (Seychelles, ×1.20); nominee director; no PSC filed. No sanctions-list MATCH. List versions in force: OFAC 2026-06-12, EU 2026-06-11. Algorithm v1.1.",
  },
  {
    id: 'ENT-20240613-8807', entity: 'Aldgate Finance Services', entityType: 'business (KYB)',
    verdict: 'REVIEW', track: 'B:risk', trackLong: 'Track B — cluster-elevated priority', threshold: 0.50,
    country: 'Cyprus', tier: 'STANDARD', transfer: 'Inbound', lists: '—', slaMins: 38, flags: ['CLUSTER ELEVATED'],
    causeHead: 'REVIEW — cluster-elevated priority',
    causeBody: 'Individual score already reaches REVIEW. Four entities each scoring ≈0.55 share a director_id / UBO — a cluster pattern. Network analysis raises queue priority for the cluster but never changes the verdict class: association → REVIEW, never an autonomous MATCH. The only graph path to MATCH is the deterministic 50% Rule.',
    pay: { amount: '$31,400', amountSub: 'SEPA · EUR', corridor: 'CY → DE', rail: 'SEPA', senderName: 'Aldgate Finance Services', senderWallet: 'CY-HE-388201', senderUbo: 'PARTIAL', receiverName: 'Rheinmark Trading GmbH', receiverWallet: 'DE-HRB-99421', receiverUbo: 'FULL', tags: [] },
    factors: [
      { name: 'Identity match signal', score: 0.40, weight: 0.25, detail: 'No list match; weak partial name overlap with a watchlist alias, below the corroboration threshold.' },
      { name: 'Behavioral / txn anomaly', score: 0.55, weight: 0.20, detail: 'Round-tripping pattern between connected SPVs; moderate velocity elevation.' },
      { name: 'Network / graph exposure', score: 0.60, weight: 0.20, detail: 'noisy-OR elevated by 3 connected REVIEW entities sharing a beneficial owner / director within 1–2 hops. Cluster context shown below.' },
      { name: 'Entity risk profile', score: 0.80, weight: 0.15, detail: 'Cyprus SPV holding entities across 3 jurisdictions; registered at agent address; multiple_jurisdictions signal.' },
      { name: 'Document / onboarding integrity', score: 0.50, weight: 0.10, detail: 'Onboarding documents consistent; no integrity flag raised.' },
      { name: 'Historical flag rate', score: 0.46, weight: 0.10, detail: 'Beta(1,9)-smoothed 0.06 over 22 screenings; 1 prior confirmed-true hit.' },
    ],
    network: { type: 'cluster', id: 'NET-2024-0058', cluster: [{ label: 'Aldgate Finance Services', sub: 'subject · 0.55', subject: true }, { label: 'Meridian Global Ltd', sub: '0.57 · shared UBO', subject: false }, { label: 'Kestrel Capital Partners', sub: '0.54 · shared director', subject: false }, { label: 'Brixton Holdings Ltd', sub: '0.55 · shared address', subject: false }], shadow: 'Shared shadow UBO across all 4 entities · queue priority elevated, verdict class unchanged (REVIEW)' },
    profile: { regNo: 'CY-HE-388201', incorporated: '2021-08', jurisdiction: 'Cyprus', structure: 'Cyprus SPV', uboStatus: 'PARTIAL', uboDepth: '2 of 3', uboName: '(shared, under review)', uboDetail: 'Shares a beneficial owner with 3 other REVIEW entities. Cluster flagged for coordinated examination.', kybStatus: 'PARTIAL', kybAddress: '—', corpFlags: ['multiple_jurisdictions', 'registered_agent_address'], adverse: [], histScreen: 22, histHits: 1, histRate: '0.06' },
    audit: "REVIEW — individual risk 0.55 (≥0.50). Cluster of 4 entities (each ≈0.55) sharing a beneficial owner / director; noisy-OR cluster context raises queue priority. Verdict class unchanged — association routes to REVIEW, never MATCH (the only graph path to MATCH is the deterministic 50% Rule). No sanctions-list MATCH. List versions: OFAC 2026-06-12, EU 2026-06-11. Algorithm v1.1.",
  },
  {
    id: 'ENT-20240613-8795', entity: 'Riverside Sports Club Ltd', entityType: 'business (KYB)',
    verdict: 'NO_MATCH', track: 'B:risk', trackLong: 'Track B — released', threshold: 0.50,
    country: 'United Kingdom', tier: 'STANDARD', transfer: 'Internal', lists: '—', slaMins: 120, flags: [],
    composite: 0.18,
    causeHead: 'NO_MATCH — released & audited',
    causeBody: 'Internal KYB↔KYB transfer; both parties FULL UBO status. Hop-trace depth reduced to 1 (internal pair); no OFAC wallet match, no issuer freeze. Risk score 0.18 is well below the 0.50 REVIEW threshold. Released and logged.',
    pay: { amount: '5,000 USDT', amountSub: '≈ $5,000', corridor: 'GB → GB', rail: 'TRON · USDT', senderName: 'Riverside Sports Club Ltd', senderWallet: 'TQ1a4…7bN3', senderUbo: 'FULL', receiverName: 'Riverside Events Ltd', receiverWallet: 'TQ9z7…2mK8', receiverUbo: 'FULL', tags: [{ k: 'INT', label: 'INTERNAL KYB↔KYB', note: 'Both wallets KYB-verified members, FULL UBO — internal risk floor, hop depth 1.' }] },
    noFactorsHead: 'Cleared below threshold', noFactorsBody: 'Track B risk 0.18 is far below the 0.50 REVIEW threshold for an internal, fully-verified pair. No factor breakdown is escalated for a clean release.',
    network: null,
    profile: { regNo: 'GB-07744120', incorporated: '2016-03', jurisdiction: 'United Kingdom', structure: 'Members club Ltd', uboStatus: 'FULL', uboDepth: '1 of 1', uboName: 'Board of trustees', uboDetail: 'All UBOs identified, verified, screened — clean. Standard monitoring tier.', kybStatus: 'FULL · internal', kybAddress: 'TQ1a4…7bN3', corpFlags: [], adverse: [], histScreen: 64, histHits: 0, histRate: '0.02' },
    audit: "NO_MATCH — RELEASED. Internal KYB↔KYB transfer, both parties FULL UBO; hop depth 1. No OFAC wallet match; no issuer freeze; Track B risk 0.18 < 0.50. Released and audited (who/what/when/why). List version in force: OFAC 2026-06-12. Algorithm v1.1.",
  },
  {
    id: 'ENT-20240613-8788', entity: 'Helios Maritime DMCC', entityType: 'business (KYB)',
    verdict: 'REVIEW', track: 'B:risk', trackLong: 'Track B — PEP enhanced due diligence', threshold: 0.50,
    country: 'United Arab Emirates', tier: 'GREY', transfer: 'Outbound', lists: 'PEP', slaMins: 52, flags: ['PEP'],
    causeHead: 'REVIEW — PEP, enhanced due diligence',
    causeBody: 'A director is a domestic Politically Exposed Person — a PEP flag without an active sanction. This is informational (blue), not a list MATCH, but mandates Enhanced Due Diligence and routes to REVIEW. The risk score reflects the PEP exposure plus a grey-list jurisdiction multiplier.',
    pay: { amount: '$74,000', amountSub: 'SWIFT · USD', corridor: 'AE → SG', rail: 'SWIFT', senderName: 'Helios Maritime DMCC', senderWallet: 'AE-DMCC-201144', senderUbo: 'FULL', receiverName: 'Strait Logistics Pte', receiverWallet: 'SG-UEN-201744K', receiverUbo: 'FULL', tags: [{ k: 'PEP', label: 'PEP — INFORMATIONAL', note: 'Domestic PEP director; EDD mandatory. No sanction — does not change the verdict class.' }] },
    factors: [
      { name: 'Identity match signal', score: 0.45, weight: 0.25, detail: 'No sanctions-list match. PEP-register hit on a director name (informational); below sanctions corroboration threshold.' },
      { name: 'Behavioral / txn anomaly', score: 0.70, weight: 0.20, detail: 'New high-value corridor; counterparty novelty; amount 3× prior maximum for this entity.' },
      { name: 'Network / graph exposure', score: 0.58, weight: 0.20, detail: 'noisy-OR moderate: 2 hops from a REVIEW entity via shared director; no SDN within 3 hops.' },
      { name: 'Entity risk profile', score: 0.92, weight: 0.15, detail: 'PEP director (EDD); UAE grey-list (×1.35); maritime sector elevated risk; otherwise clean structure.' },
      { name: 'Document / onboarding integrity', score: 0.60, weight: 0.10, detail: 'Beneficial-ownership declaration consistent; minor address mismatch flagged.' },
      { name: 'Historical flag rate', score: 0.48, weight: 0.10, detail: 'Beta(1,9)-smoothed 0.05 over 31 screenings.' },
    ],
    network: null,
    profile: { regNo: 'AE-DMCC-201144', incorporated: '2018-09', jurisdiction: 'UAE · DMCC', structure: 'Free-zone LLC', uboStatus: 'FULL', uboDepth: '2 of 2', uboName: 'Director flagged PEP', uboDetail: 'All UBOs identified and screened; one director is a domestic PEP. Enhanced monitoring; 18-month lookback applies.', kybStatus: 'FULL', kybAddress: '—', corpFlags: ['pep_director'], adverse: [{ src: 'Gulf News', date: '2023-07-19', rel: 0.51 }], histScreen: 31, histHits: 0, histRate: '0.05' },
    audit: "REVIEW — Track B risk 0.61 (≥0.50). PEP director identified on the PEP register (informational, no sanction) → mandatory Enhanced Due Diligence. UAE grey-list (×1.35); new high-value corridor, counterparty novelty. No sanctions-list MATCH; verdict class driven by EDD + risk score. List versions: OFAC 2026-06-12, EU 2026-06-11. Algorithm v1.1.",
  },
  {
    id: 'ENT-20240613-8781', entity: 'Blue Harbor Logistics LLC', entityType: 'business (KYB)',
    verdict: 'REVIEW', track: 'B:risk', trackLong: 'Track B + MiCA / TRON policy flags', threshold: 0.50,
    country: 'Germany', tier: 'STANDARD', transfer: 'Outbound', lists: '—', slaMins: 61, flags: ['MiCA', 'TRON·EU'],
    causeHead: 'REVIEW — risk + MiCA / TRON policy review',
    causeBody: 'Track B risk escalates to REVIEW. Two informational policy flags attach: USDT is not MiCA-authorised (mid-2026) on this EU corridor, and TRON/USDT settlement on a EU corridor carries the TRON_EU_CORRIDOR_REVIEW flag. Both prompt legal review; neither changes the numeric score.',
    pay: { amount: '29,000 USDT', amountSub: '≈ $29,000', corridor: 'DE → AE', rail: 'TRON · USDT', senderName: 'Blue Harbor Logistics LLC', senderWallet: 'TZ4h2…1pX7', senderUbo: 'FULL', receiverName: 'Gulf Freight DMCC', receiverWallet: 'TR6n5…5vB2', receiverUbo: 'PARTIAL', tags: [{ k: 'MiCA', label: 'MiCA_COMPLIANCE_RISK', note: 'USDT not MiCA-authorised; EU corridor → legal review.' }, { k: 'TRON', label: 'TRON_EU_CORRIDOR_REVIEW', note: 'TRON/USDT on a EU corridor — policy flag, no score change.' }] },
    factors: [
      { name: 'Identity match signal', score: 0.35, weight: 0.25, detail: 'No list match; clean name screen against all required lists.' },
      { name: 'Behavioral / txn anomaly', score: 0.60, weight: 0.20, detail: 'Slightly elevated velocity; counterparty in a grey-list-adjacent corridor.' },
      { name: 'Network / graph exposure', score: 0.45, weight: 0.20, detail: 'noisy-OR low-moderate: no SDN within 3 hops; 1 connected REVIEW entity at 2 hops.' },
      { name: 'Entity risk profile', score: 0.80, weight: 0.15, detail: 'TRON/USDT EU corridor (MiCA grey zone); beneficiary UBO PARTIAL; otherwise standard tier.' },
      { name: 'Document / onboarding integrity', score: 0.55, weight: 0.10, detail: 'Documents consistent; no integrity flag.' },
      { name: 'Historical flag rate', score: 0.45, weight: 0.10, detail: 'Beta(1,9)-smoothed 0.04 over 48 screenings.' },
    ],
    network: null,
    profile: { regNo: 'DE-HRB-118402', incorporated: '2020-01', jurisdiction: 'Germany', structure: 'GmbH', uboStatus: 'FULL', uboDepth: '2 of 2', uboName: 'Verified (clean)', uboDetail: 'All UBOs identified and screened. Beneficiary side UBO PARTIAL → enhanced monitoring on receipt.', kybStatus: 'FULL', kybAddress: 'TZ4h2…1pX7', corpFlags: ['mica_grey_zone'], adverse: [], histScreen: 48, histHits: 0, histRate: '0.04' },
    audit: "REVIEW — Track B risk 0.52 (≥0.50). Policy flags: MiCA_COMPLIANCE_RISK (USDT not MiCA-authorised on EU corridor) and TRON_EU_CORRIDOR_REVIEW — both informational, prompting legal review without changing the score. No sanctions-list MATCH. List versions: OFAC 2026-06-12, EU 2026-06-11. Algorithm v1.1.",
  },
];

export function composite(c: Case): number | null {
  if (c.factors) { let r = 0; c.factors.forEach(f => r += f.score * f.weight); return Math.min(1, r); }
  return (typeof c.composite === 'number') ? c.composite : null;
}
