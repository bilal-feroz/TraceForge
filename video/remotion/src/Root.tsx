import "./index.css";
import { Composition, Still } from "remotion";
import { TraceForgeDemo } from "./TraceForgeDemo";
import { TraceForgeThumbnail } from "./Thumbnail";
import { FPS, HEIGHT, TOTAL_FRAMES, WIDTH } from "./theme";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="TraceForgeDemo"
        component={TraceForgeDemo}
        durationInFrames={TOTAL_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        defaultProps={{
          debug: false,
          reducedMotion: false,
          playNarration: false,
        }}
      />
      <Still
        id="TraceForgeThumbnail"
        component={TraceForgeThumbnail}
        width={1280}
        height={720}
      />
    </>
  );
};
