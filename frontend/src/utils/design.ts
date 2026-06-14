export const C = {
  MATCH: '#DC2626', REVIEW: '#D97706', NO_MATCH: '#16A34A',
  CLUSTER: '#7C3AED', PENDING: '#6B7280', INFO: '#2563EB', UBO: '#EA580C',
};

export function vMeta(v: string) {
  if (v === 'MATCH')    return { color: '#DC2626', bg: '#FCEBEB', border: '#F3C9C9' };
  if (v === 'NO_MATCH') return { color: '#16A34A', bg: '#E9F6EE', border: '#BFE4CC' };
  return { color: '#D97706', bg: '#FBF1E2', border: '#EFD7AE' };
}

export function tierMeta(t: string) {
  const m: Record<string, { fg: string; bg: string }> = {
    BLACK:     { fg: '#fff',    bg: '#14171C' },
    GREY:      { fg: '#5A6472', bg: '#ECEEF1' },
    HIGH_RISK: { fg: '#B23A1E', bg: '#FBE9E2' },
    OFFSHORE:  { fg: '#7C5E10', bg: '#F6F0DA' },
    STANDARD:  { fg: '#5A8B6A', bg: '#EAF4EE' },
  };
  return m[t] || m.STANDARD;
}

export function flagMeta(label: string) {
  const u = label.toUpperCase();
  if (u.includes('CLUSTER')) return { color: C.CLUSTER, bg: '#F1EAFB', border: '#DDC9F5' };
  if (u.includes('UBO'))     return { color: C.UBO,     bg: '#FDEEE5', border: '#F7CFB5' };
  return { color: C.INFO, bg: '#E8F0FD', border: '#C3D8F8' };
}

export function uboMeta(s: string) {
  s = s || '';
  if (s.includes('FULL'))                          return { color: '#16A34A', bg: '#E9F6EE', border: '#BFE4CC' };
  if (s.includes('UNRESOLVED'))                    return { color: '#EA580C', bg: '#FDEEE5', border: '#F7CFB5' };
  if (s.includes('EXTERNAL') || s === 'N/A')       return { color: '#6B7280', bg: '#EEF0F3', border: '#D8DCE1' };
  return { color: '#D97706', bg: '#FBF1E2', border: '#EFD7AE' };
}

export function slaMeta(m: number) {
  let color: string, halo: string;
  if (m < 15)      { color = '#DC2626'; halo = 'rgba(220,38,38,0.16)'; }
  else if (m < 45) { color = '#D97706'; halo = 'rgba(217,119,6,0.16)'; }
  else             { color = '#6B7280'; halo = 'rgba(107,114,128,0.14)'; }
  const label = m >= 60 ? (m / 60).toFixed(1).replace('.0', '') + 'h' : m + 'm';
  return { color, halo, label };
}

export function tint(score: number) {
  const L = Math.round(77 - score * 40);
  return `hsl(30 80% ${L}%)`;
}
