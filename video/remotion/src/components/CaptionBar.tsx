import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { colors, fonts } from "../theme";

export const CaptionBar: React.FC<{
  lines: string[];
  start?: number;
  end?: number;
}> = ({ lines, start = 0, end = 99999 }) => {
  const frame = useCurrentFrame();
  if (frame < start || frame > end || lines.length === 0) {
    return null;
  }
  const opacity = interpolate(
    frame,
    [start, start + 8, Math.max(start + 9, end - 8), end],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 48,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          opacity,
          maxWidth: 1400,
          background: "rgba(14, 17, 22, 0.82)",
          border: `1px solid ${colors.borderStrong}`,
          padding: "14px 28px",
          textAlign: "center",
        }}
      >
        {lines.map((line) => (
          <div
            key={line}
            style={{
              fontFamily: fonts.display,
              fontSize: 30,
              fontWeight: 500,
              color: colors.paper,
              lineHeight: 1.35,
            }}
          >
            {line}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
