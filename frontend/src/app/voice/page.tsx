"use client";

import React, { useState } from "react";
import { Activity, Mic, Shield, Volume2 } from "lucide-react";
import { BrandLoader } from "@/components/BrandLoader";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi } from "@/lib/api";

const SUPPORTED_LANGUAGES = [
  "Hindi", "English", "Hinglish", "Bengali", "Tamil", "Telugu", "Gujarati",
  "Marathi", "Punjabi", "Kannada", "Malayalam", "Urdu", "Assamese", "Odia",
];

const VOICE_PERSONALITIES = [
  { id: "aanya-warm", label: "Aanya — Warm Companion (en-IN / hi-IN)" },
  { id: "kavya-executive", label: "Kavya — Crisp Executive (en-IN)" },
  { id: "meera-mentor", label: "Meera — Calm Study Mentor (hi-IN)" },
  { id: "riya-hinglish", label: "Riya — Expressive Hinglish" },
];

export default function VoicePage() {
  const [transcript, setTranscript] = useState("Hey Nova bhai aaj ka plan batao");
  const [personality, setPersonality] = useState("aanya-warm");
  const [listenMode, setListenMode] = useState<"always" | "ptt" | "wake">("always");
  const [busy, setBusy] = useState(false);
  const [micReport, setMicReport] = useState(
    "Run automatic microphone diagnostics to inspect Windows audio input devices and repair tips."
  );
  const [resultSummary, setResultSummary] = useState(
    "Live Companion Mode active — auto-detects language (including Hinglish), retains language memory, and checks speaker verification."
  );

  return (
    <WorkspaceShell routeId="voice">
      {({ token, setStatusNote }) => (
        <div className="space-y-5">
          <GlassCard>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Mic className="h-6 w-6 text-sky-500 dark:text-sky-400" />
                <div>
                  <h2 className="text-lg font-bold">
                    Live AI Companion &amp; Multilingual Voice Studio
                  </h2>
                  <p className="text-xs text-adaptive-muted">
                    Streaming dialogue &bull; 14 Languages + Hinglish &bull; Personalities &bull; Mic Diagnostics &bull; Speaker ID
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-xs">
                <label htmlFor="listen-mode-select" className="sr-only">
                  Voice Activation Mode
                </label>
                <select
                  id="listen-mode-select"
                  value={listenMode}
                  onChange={(e) => setListenMode(e.target.value as "always" | "ptt" | "wake")}
                  className="select-surface rounded-xl px-3 py-1.5 text-xs font-semibold outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                >
                  <option value="always">Always-Listening Mode</option>
                  <option value="wake">Wake Word (&ldquo;Hey Nova&rdquo;)</option>
                  <option value="ptt">Push-to-Talk Mode</option>
                </select>
                <label htmlFor="voice-personality-select" className="sr-only">
                  Voice Personality
                </label>
                <select
                  id="voice-personality-select"
                  value={personality}
                  onChange={(e) => setPersonality(e.target.value)}
                  className="select-surface rounded-xl px-3 py-1.5 text-xs font-semibold outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                >
                  {VOICE_PERSONALITIES.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-4 flex flex-col gap-3 sm:flex-row">
              <label htmlFor="voice-transcript" className="sr-only">
                Voice Transcript
              </label>
              <input
                id="voice-transcript"
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                className="input-surface flex-1 rounded-xl px-3 py-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
              />
              <button
                type="button"
                onClick={async () => {
                  setBusy(true);
                  try {
                    if (token) {
                      const res = await ecosystemApi.voiceProcess(token, {
                        transcript,
                        always_listening: listenMode === "always",
                        noise_db: -42,
                      });
                      setResultSummary(
                        `Lang=${res.language_name} | Intent=${res.detected_intent} | Confidence=${res.confidence} | Access=${res.access_level} | Reply: ${res.reply_text}`
                      );
                      setStatusNote(`Processed live utterance in ${res.language_name}.`);
                    } else {
                      setResultSummary(
                        `Preview (${personality}, mode=${listenMode}): detected Hindi/Hinglish code-switching & queued interruptible reply.`
                      );
                    }
                  } finally {
                    setBusy(false);
                  }
                }}
                className="inline-flex min-h-[40px] items-center justify-center gap-1.5 rounded-xl bg-aspirant-gradient px-4 py-2 text-xs font-semibold text-white"
              >
                <Volume2 className="h-3.5 w-3.5" /> Speak &amp; Preview
              </button>
            </div>

            {busy && (
              <div className="mt-3">
                <BrandLoader label="Streaming multilingual neural response..." size={32} />
              </div>
            )}

            <p className="surface-card mt-3 rounded-xl p-3 text-xs text-sky-700 dark:text-sky-300">
              {resultSummary}
            </p>
          </GlassCard>

          <div className="grid gap-4 md:grid-cols-2">
            <GlassCard>
              <h3 className="text-sm font-bold text-sky-600 dark:text-sky-400">
                14 Supported Languages + Code-Switching
              </h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {SUPPORTED_LANGUAGES.map((lang) => (
                  <span key={lang} className="surface-card rounded-lg px-2.5 py-1 text-xs font-medium">
                    {lang}
                  </span>
                ))}
              </div>
            </GlassCard>

            <GlassCard>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-violet-600 dark:text-violet-400">
                  <Activity className="h-4 w-4" />
                  <h3 className="text-sm font-bold">Automatic Mic Test &amp; Speaker ID</h3>
                </div>
                <button
                  type="button"
                  onClick={async () => {
                    if (token) {
                      const diag = await ecosystemApi.voiceAudioDiagnostics(token);
                      setMicReport(
                        `Status=${diag.health_status} | Inputs=${diag.input_devices.length} | Outputs=${diag.output_devices.length} | Guidance: ${diag.repair_guidance.join("; ")}`
                      );
                      setStatusNote(`Audio diagnostics: ${diag.health_status}.`);
                    } else {
                      setMicReport("Preview: Probed default Windows WASAPI microphone & speakers; connect JWT for live device list.");
                    }
                  }}
                  className="surface-card min-h-[36px] rounded-lg px-3 py-1 text-xs font-semibold hover:border-sky-500"
                >
                  Run Audio Diagnostics
                </button>
              </div>
              <p className="mt-2 text-xs text-adaptive-body">{micReport}</p>
              <p className="mt-2 flex items-center gap-1.5 text-[11px] text-adaptive-muted">
                <Shield className="h-3.5 w-3.5 text-emerald-500" />
                Voice cloning hooks &amp; speaker verification require password fallback for changes.
              </p>
            </GlassCard>
          </div>
        </div>
      )}
    </WorkspaceShell>
  );
}
