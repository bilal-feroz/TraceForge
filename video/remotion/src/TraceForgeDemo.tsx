import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { CaptionBar } from "./components/CaptionBar";
import { captions, scenes } from "./data/timeline";
import {
  BaselineScene,
  CandidateScene,
  ClosingScene,
  HookScene,
  LatencyScene,
  PatchAuditScene,
  PatchedScene,
  ProblemScene,
  ProductScene,
  RootCauseScene,
  SignozScene,
  TrustScene,
} from "./scenes/Scenes";
import { TOTAL_FRAMES } from "./theme";

const sceneComponents = {
  hook: HookScene,
  problem: ProblemScene,
  product: ProductScene,
  baseline: BaselineScene,
  candidate: CandidateScene,
  signoz: SignozScene,
  rootCause: RootCauseScene,
  patchAudit: PatchAuditScene,
  patched: PatchedScene,
  latency: LatencyScene,
  trust: TrustScene,
  closing: ClosingScene,
} as const;

export type DemoProps = {
  debug: boolean;
  reducedMotion: boolean;
  playNarration: boolean;
};

export const TraceForgeDemo: React.FC<DemoProps> = ({
  debug,
  playNarration,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#0E1116" }}>
      {scenes.map((scene) => {
        const Component = sceneComponents[scene.id];
        return (
          <Sequence key={scene.id} from={scene.from} durationInFrames={scene.duration} name={scene.id}>
            <Component />
          </Sequence>
        );
      })}

      {captions.map((cue, index) => (
        <CaptionBar key={`${cue.scene}-${index}`} lines={cue.lines} start={cue.start} end={cue.end} />
      ))}

      {playNarration ? (
        <Audio src={staticFile("audio/narration-full.wav")} volume={1} />
      ) : null}

      {debug ? (
        <AbsoluteFill
          style={{
            pointerEvents: "none",
            border: "2px dashed rgba(232,107,44,0.35)",
            margin: 72,
            width: "auto",
            height: "auto",
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};

export const DEMO_DURATION = TOTAL_FRAMES;
