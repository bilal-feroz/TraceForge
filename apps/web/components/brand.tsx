import Link from "next/link";

export function ForgeMark() {
  return (
    <svg
      aria-hidden="true"
      className="forge-mark"
      fill="none"
      height="38"
      viewBox="0 0 40 40"
      width="38"
    >
      <path d="M4 5h26l6 6v24H10l-6-6V5Z" stroke="#ff7a32" strokeWidth="1.4" />
      <path d="M10 12h19M10 18h14M10 24h19M16 30h13" stroke="#39d9e6" strokeWidth="1.4" />
      <path d="m4 29 6 6V11L4 5v24Z" fill="#ff7a32" fillOpacity=".16" />
    </svg>
  );
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link
      aria-label="TraceForge control room"
      className="flex items-center gap-3 text-[var(--paper)] no-underline"
      href="/"
    >
      <ForgeMark />
      {!compact && (
        <span>
          <span className="block text-[0.96rem] font-semibold tracking-[0.035em]">TraceForge</span>
          <span className="eyebrow mt-0.5 block text-[0.55rem]">Reliability flight recorder</span>
        </span>
      )}
    </Link>
  );
}

