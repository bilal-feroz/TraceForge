import React from "react";
import { AbsoluteFill } from "remotion";

export const SafeArea: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <AbsoluteFill
      style={{
        padding: "72px 96px 96px",
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
