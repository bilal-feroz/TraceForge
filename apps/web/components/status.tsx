import type { TerminalState } from "@/lib/types";

const styles: Record<string, string> = {
  PASSED: "text-[var(--green)] border-[color:rgba(73,209,125,.3)] bg-[rgba(73,209,125,.08)]",
  SHIP: "text-[var(--green)] border-[color:rgba(73,209,125,.3)] bg-[rgba(73,209,125,.08)]",
  BLOCKED: "text-[var(--red)] border-[color:rgba(255,92,97,.3)] bg-[rgba(255,92,97,.08)]",
  BLOCK: "text-[var(--red)] border-[color:rgba(255,92,97,.3)] bg-[rgba(255,92,97,.08)]",
  FAILED: "text-[var(--red)] border-[color:rgba(255,92,97,.3)] bg-[rgba(255,92,97,.08)]",
  NEEDS_REVIEW:
    "text-[var(--amber)] border-[color:rgba(243,189,78,.3)] bg-[rgba(243,189,78,.08)]",
  CANCELLED: "text-[var(--steel-300)] border-white/15 bg-white/[.04]",
  ACTIVE: "text-[var(--ember)] border-[color:rgba(255,122,50,.3)] bg-[rgba(255,122,50,.08)]",
};

export function StatusBadge({
  value,
  label,
}: {
  value: TerminalState | "SHIP" | "BLOCK" | "ACTIVE";
  label?: string;
}) {
  return (
    <span
      className={`mono inline-flex items-center gap-2 border px-2.5 py-1 text-[0.66rem] font-semibold tracking-[.08em] ${styles[value]}`}
    >
      <span className={`status-dot ${value === "ACTIVE" ? "live-pulse" : ""}`} />
      {label ?? value.replace("_", " ")}
    </span>
  );
}

export function Availability({
  available,
  availableText = "Connected",
  unavailableText = "Unavailable",
}: {
  available: boolean;
  availableText?: string;
  unavailableText?: string;
}) {
  return (
    <span
      className={`mono inline-flex items-center gap-2 text-xs ${
        available ? "text-[var(--cyan)]" : "text-[var(--amber)]"
      }`}
    >
      <span className="status-dot" />
      {available ? availableText : unavailableText}
    </span>
  );
}

