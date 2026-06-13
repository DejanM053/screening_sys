import type { Decision, TransferType, UboStatus, Verdict } from "../types";
import { CLUSTER_COLOR, INFO_COLOR, PENDING_COLOR, UBO_COLOR, VERDICT_COLORS } from "../types";

function Pill({
  label,
  color,
  title,
}: {
  label: string;
  color: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wide"
      style={{ color, borderColor: color, borderWidth: 1, backgroundColor: `${color}1A` }}
    >
      {label}
    </span>
  );
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return <Pill label={verdict} color={VERDICT_COLORS[verdict]} />;
}

export function UboBadge({ status }: { status: UboStatus }) {
  const color = status === "FULL" ? VERDICT_COLORS.NO_MATCH : status === "PARTIAL" ? VERDICT_COLORS.REVIEW : UBO_COLOR;
  return <Pill label={`UBO: ${status}`} color={color} title="Beneficial ownership resolution status" />;
}

export function ClusterBadge({ label = "CLUSTER ELEVATED" }: { label?: string }) {
  return <Pill label={label} color={CLUSTER_COLOR} />;
}

export function PendingBadge({ label = "PENDING" }: { label?: string }) {
  return <Pill label={label} color={PENDING_COLOR} />;
}

export function PolicyFlagBadge({ flag }: { flag: string }) {
  const labels: Record<string, string> = {
    MiCA_COMPLIANCE_RISK: "MiCA COMPLIANCE RISK",
    TRON_EU_CORRIDOR_REVIEW: "TRON EU CORRIDOR",
    pep_flag: "PEP",
  };
  return <Pill label={labels[flag] ?? flag} color={INFO_COLOR} />;
}

export function TransferTypeBadge({ type }: { type: TransferType }) {
  const colors: Record<TransferType, string> = {
    INTERNAL: VERDICT_COLORS.NO_MATCH,
    OUTBOUND: VERDICT_COLORS.REVIEW,
    INBOUND: VERDICT_COLORS.MATCH,
  };
  return <Pill label={type} color={colors[type]} />;
}

export function SlaBadge({ slaDeadline }: { slaDeadline: string }) {
  const remainingMs = new Date(slaDeadline).getTime() - Date.now();
  const remainingHours = remainingMs / (1000 * 60 * 60);

  let color = VERDICT_COLORS.NO_MATCH;
  let label = `${remainingHours.toFixed(1)}h left`;
  if (remainingHours <= 0) {
    color = VERDICT_COLORS.MATCH;
    label = "OVERDUE";
  } else if (remainingHours < 1) {
    color = VERDICT_COLORS.MATCH;
  } else if (remainingHours <= 4) {
    color = VERDICT_COLORS.REVIEW;
  }

  return <Pill label={label} color={color} title={`SLA deadline: ${new Date(slaDeadline).toLocaleString()}`} />;
}

export function DecisionBadge({ decision }: { decision: Decision }) {
  const colors: Record<Decision, string> = {
    CLEAR: VERDICT_COLORS.NO_MATCH,
    BLOCK: VERDICT_COLORS.MATCH,
    ESCALATE: CLUSTER_COLOR,
    REQUEST_INFO: INFO_COLOR,
    DEFER: PENDING_COLOR,
  };
  return <Pill label={decision.replace("_", " ")} color={colors[decision]} />;
}
