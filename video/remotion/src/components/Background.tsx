import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { colors } from "../theme";

export const Background: React.FC<{
  accent?: "ember" | "cyan" | "red" | "green" | "amber" | "none";
}> = ({ accent = "none" }) => {
  const frame = useCurrentFrame();
  const drift = interpolate(frame, [0, 300], [0, 18], {
    extrapolateRight: "extend",
  });
  const glow =
    accent === "ember"
      ? "rgba(232, 107, 44, 0.16)"
      : accent === "cyan"
        ? "rgba(61, 184, 197, 0.14)"
        : accent === "red"
          ? "rgba(224, 90, 90, 0.14)"
          : accent === "green"
            ? "rgba(61, 191, 122, 0.12)"
            : accent === "amber"
              ? "rgba(212, 160, 23, 0.14)"
              : "transparent";

  return (
    <AbsoluteFill
      style={{
        backgroundColor: colors.graphite,
        backgroundImage: `
          radial-gradient(ellipse 900px 520px at ${22 + drift * 0.2}% 18%, ${glow}, transparent 70%),
          radial-gradient(ellipse 700px 480px at 88% 82%, rgba(61, 184, 197, 0.06), transparent 65%),
          linear-gradient(${colors.graphite}, ${colors.graphiteRaised})
        `,
      }}
    >
      <AbsoluteFill
        style={{
          opacity: 0.18,
          backgroundImage: `
            linear-gradient(rgba(240,243,246,0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(240,243,246,0.05) 1px, transparent 1px)
          `,
          backgroundSize: "64px 64px",
          transform: `translateY(${drift % 64}px)`,
        }}
      />
    </AbsoluteFill>
  );
};
