/**
 * Optional TTS narration generator.
 *
 * Reads keys only from video/.env.local (ignored) — never from the TraceForge root .env.
 * Supported:
 *   ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID
 *   OPENAI_API_KEY (tts-1)
 *
 * If no key is present, exits 0 after writing a status file so the silent render can proceed.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const videoRoot = path.resolve(__dirname, "..");
const scriptPath = path.join(videoRoot, "assets/audio/narration-script.json");
const outDir = path.join(videoRoot, "assets/audio/narration");
const statusPath = path.join(outDir, "STATUS.json");
const envPath = path.join(videoRoot, ".env.local");

mkdirSync(outDir, { recursive: true });

function loadEnvLocal() {
  if (!existsSync(envPath)) return {};
  const env = {};
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const eq = trimmed.indexOf("=");
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

const env = loadEnvLocal();
const script = JSON.parse(readFileSync(scriptPath, "utf8"));

async function synthesizeOpenAI(text, dest) {
  const response = await fetch("https://api.openai.com/v1/audio/speech", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "tts-1",
      voice: env.OPENAI_TTS_VOICE || "alloy",
      input: text,
      response_format: "wav",
    }),
  });
  if (!response.ok) {
    throw new Error(`OpenAI TTS failed with HTTP ${response.status}`);
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  writeFileSync(dest, buffer);
}

async function synthesizeElevenLabs(text, dest) {
  const voice = env.ELEVENLABS_VOICE_ID;
  const response = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${voice}?output_format=wav_44100`,
    {
      method: "POST",
      headers: {
        "xi-api-key": env.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        Accept: "audio/wav",
      },
      body: JSON.stringify({
        text,
        model_id: env.ELEVENLABS_MODEL_ID || "eleven_multilingual_v2",
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`ElevenLabs TTS failed with HTTP ${response.status}`);
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  writeFileSync(dest, buffer);
}

const provider = env.ELEVENLABS_API_KEY
  ? "elevenlabs"
  : env.OPENAI_API_KEY
    ? "openai"
    : null;

if (!provider) {
  writeFileSync(
    statusPath,
    JSON.stringify(
      {
        generated: false,
        reason:
          "No TTS key found in video/.env.local. Silent preview remains available. Add OPENAI_API_KEY or ELEVENLABS_API_KEY there — never to the TraceForge root .env.",
      },
      null,
      2,
    ),
  );
  console.log("No TTS credentials in video/.env.local — skipping audio generation.");
  process.exit(0);
}

const results = [];
for (const [index, scene] of script.scenes.entries()) {
  const filename = `${String(index + 1).padStart(2, "0")}-${scene.id}.wav`;
  const dest = path.join(outDir, filename);
  process.stdout.write(`Generating ${filename} via ${provider}… `);
  if (provider === "openai") {
    await synthesizeOpenAI(scene.narration, dest);
  } else {
    await synthesizeElevenLabs(scene.narration, dest);
  }
  console.log("ok");
  results.push({ id: scene.id, file: filename, bytes: readFileSync(dest).byteLength });
}

writeFileSync(
  statusPath,
  JSON.stringify({ generated: true, provider, clips: results }, null, 2),
);
console.log(`Wrote ${results.length} narration clips to ${outDir}`);
