import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { colors, fonts } from "../theme";

type Tone = "neutral" | "ember" | "cyan" | "red" | "green" | "amber";

const toneColor: Record<Tone, string> = {
  neutral: colors.paper,
  ember: colors.ember,
  cyan: colors.cyan,
  red: colors.red,
  green: colors.green,
  amber: colors.amber,
};

export const MetricCard: React.FC<{
  label: string;
  value: string;
  hint?: string;
  tone?: Tone;
  delay?: number;
  width?: number;
}> = ({ label, value, hint, tone = "neutral", delay = 0, width = 280 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({
    frame: frame - delay,
    fps,
    config: { damping: 200 },
  });
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const y = interpolate(enter, [0, 1], [24, 0]);

  return (
    <div
      style={{
        width,
        opacity,
        transform: `translateY(${y}px)`,
        background: colors.graphitePanel,
        border: `1px solid ${colors.borderStrong}`,
        borderLeft: `4px solid ${toneColor[tone]}`,
        padding: "22px 24px",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          fontFamily: fonts.mono,
          fontSize: 16,
          letterSpacing: "0.12em",
          color: colors.steel,
          textTransform: "uppercase",
          marginBottom: 10,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: fonts.display,
          fontSize: 44,
          fontWeight: 650,
          color: toneColor[tone],
          lineHeight: 1.05,
        }}
      >
        {value}
      </div>
      {hint ? (
        <div
          style={{
            marginTop: 10,
            fontFamily: fonts.mono,
            fontSize: 15,
            color: colors.paperMuted,
          }}
        >
          {hint}
        </div>
      ) : null}
    </div>
  );
};
