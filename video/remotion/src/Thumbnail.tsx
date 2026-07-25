import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { colors, fonts } from "./theme";

export const TraceForgeThumbnail: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: colors.graphite }}>
      <Img
        src={staticFile("screenshots/candidate-02-error-rate-and-status.png")}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: 0.28,
          filter: "saturate(0.85)",
        }}
      />
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(115deg, rgba(14,17,22,0.96) 18%, rgba(14,17,22,0.78) 55%, rgba(14,17,22,0.55) 100%)",
        }}
      />
      <AbsoluteFill style={{ padding: "56px 64px", justifyContent: "space-between" }}>
        <div>
          <div
            style={{
              fontFamily: fonts.mono,
              fontSize: 22,
              letterSpacing: "0.18em",
              color: colors.ember,
              textTransform: "uppercase",
            }}
          >
            TraceForge
          </div>
          <div
            style={{
              marginTop: 28,
              fontFamily: fonts.display,
              fontSize: 68,
              fontWeight: 700,
              color: colors.paper,
              lineHeight: 1.05,
              maxWidth: 760,
            }}
          >
            AI found the regression
            <br />
            and proved the fix
          </div>
        </div>
        <div style={{ display: "flex", gap: 16, alignItems: "stretch" }}>
          {[
            { label: "BASELINE", value: "HEALTHY", color: colors.cyan },
            { label: "CANDIDATE", value: "94.40% FAIL", color: colors.red },
            { label: "PATCHED", value: "VERIFIED", color: colors.green },
          ].map((item) => (
            <div
              key={item.label}
              style={{
                minWidth: 220,
                padding: "18px 20px",
                border: `1px solid ${item.color}`,
                background: "rgba(14,17,22,0.82)",
              }}
            >
              <div
                style={{
                  fontFamily: fonts.mono,
                  fontSize: 16,
                  letterSpacing: "0.12em",
                  color: colors.steel,
                }}
              >
                {item.label}
              </div>
              <div
                style={{
                  marginTop: 10,
                  fontFamily: fonts.display,
                  fontSize: 32,
                  fontWeight: 700,
                  color: item.color,
                }}
              >
                {item.value}
              </div>
            </div>
          ))}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
