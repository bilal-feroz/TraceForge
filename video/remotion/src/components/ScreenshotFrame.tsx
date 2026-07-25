import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { colors, fonts } from "../theme";

export const ScreenshotFrame: React.FC<{
  src: string;
  label?: string;
  zoom?: number;
  focusX?: number;
  focusY?: number;
  delay?: number;
  dim?: number;
}> = ({
  src,
  label,
  zoom = 1.08,
  focusX = 50,
  focusY = 40,
  delay = 0,
  dim = 0.35,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const enter = spring({
    frame: frame - delay,
    fps,
    config: { damping: 200 },
  });
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const scale = interpolate(
    frame,
    [delay, Math.max(delay + 8, durationInFrames - 6)],
    [1.02, zoom],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <div
      style={{
        opacity,
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        gap: 14,
      }}
    >
      {label ? (
        <div
          style={{
            fontFamily: fonts.mono,
            fontSize: 18,
            letterSpacing: "0.14em",
            color: colors.cyan,
            textTransform: "uppercase",
          }}
        >
          {label}
        </div>
      ) : null}
      <div
        style={{
          flex: 1,
          border: `1px solid ${colors.borderStrong}`,
          background: "#05070A",
          boxShadow: "0 24px 80px rgba(0,0,0,0.45)",
          overflow: "hidden",
          position: "relative",
        }}
      >
        <div
          style={{
            height: 34,
            borderBottom: `1px solid ${colors.border}`,
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "0 14px",
            background: colors.graphiteRaised,
          }}
        >
          <span style={{ width: 10, height: 10, borderRadius: 999, background: "#5C6570" }} />
          <span style={{ width: 10, height: 10, borderRadius: 999, background: "#5C6570" }} />
          <span style={{ width: 10, height: 10, borderRadius: 999, background: "#5C6570" }} />
          <span
            style={{
              marginLeft: 12,
              fontFamily: fonts.mono,
              fontSize: 13,
              color: colors.steel,
            }}
          >
            SigNoz · TraceForge — Release Proof
          </span>
        </div>
        <AbsoluteFill style={{ top: 34 }}>
          <Img
            src={staticFile(src)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: `${focusX}% ${focusY}%`,
              transform: `scale(${scale})`,
            }}
          />
          <AbsoluteFill
            style={{
              background: `linear-gradient(180deg, rgba(14,17,22,${dim * 0.35}) 0%, rgba(14,17,22,${dim}) 100%)`,
              pointerEvents: "none",
            }}
          />
        </AbsoluteFill>
      </div>
    </div>
  );
};
