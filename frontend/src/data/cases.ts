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

export function composite(c: Case): number | null {
  if (c.factors) { let r = 0; c.factors.forEach(f => r += f.score * f.weight); return Math.min(1, r); }
  return (typeof c.composite === 'number') ? c.composite : null;
}
