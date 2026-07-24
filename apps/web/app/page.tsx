import { ControlRoom } from "@/components/control-room";
import { Shell } from "@/components/shell";

function SystemAside() {
  return (
    <div className="sticky top-8 space-y-8">
      <section>
        <p className="eyebrow mb-4">Run doctrine</p>
        <ol className="space-y-4">
          {["Scope", "Stress", "Observe", "Diagnose", "Forge", "Prove"].map((label, index) => (
            <li className="flex items-center gap-3" key={label}>
              <span className="mono flex size-7 items-center justify-center border border-white/15 text-[0.62rem] text-[var(--steel-500)]">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="text-sm text-[var(--steel-300)]">{label}</span>
            </li>
          ))}
        </ol>
      </section>
      <div className="h-px ember-line" />
      <section>
        <p className="eyebrow mb-3">Hard gate</p>
        <p className="text-sm leading-6 text-[var(--steel-300)]">
          A model can explain evidence. It cannot rewrite latency deltas, legal transitions, or the
          final proof gate.
        </p>
      </section>
    </div>
  );
}

export default function Page() {
  return (
    <Shell aside={<SystemAside />}>
      <ControlRoom />
    </Shell>
  );
}

