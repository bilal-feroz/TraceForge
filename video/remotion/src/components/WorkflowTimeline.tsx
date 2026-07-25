import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { colors, fonts } from "../theme";

const stages = [
  "INSPECT",
  "STRESS",
  "OBSERVE",
  "DIAGNOSE",
  "FORGE",
  "AUDIT",
  "PROVE",
] as const;

export const WorkflowTimeline: React.FC<{ delay?: number }> = ({ delay = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      {stages.map((stage, index) => {
        const local = spring({
          frame: frame - delay - index * 8,
          fps,
          config: { damping: 200 },
        });
        const opacity = interpolate(local, [0, 1], [0, 1]);
        const isObserve = stage === "OBSERVE";
        return (
          <React.Fragment key={stage}>
            <div
              style={{
                opacity,
                padding: "12px 18px",
                border: `1px solid ${isObserve ? colors.cyan : colors.borderStrong}`,
                background: isObserve ? "rgba(61,184,197,0.12)" : colors.graphitePanel,
                color: isObserve ? colors.cyan : colors.paper,
                fontFamily: fonts.mono,
                fontSize: 22,
                letterSpacing: "0.08em",
              }}
            >
              {stage}
            </div>
            {index < stages.length - 1 ? (
              <div style={{ opacity, color: colors.steel, fontSize: 22 }}>→</div>
            ) : null}
          </React.Fragment>
        );
      })}
    </div>
  );
};
