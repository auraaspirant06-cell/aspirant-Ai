"use client";

import React, { useState } from "react";
import { Mic, Shield, Volume2 } from "lucide-react";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi } from "@/lib/api";

const SUPPORTED_LANGUAGES = [
  "Hindi", "English", "Bengali", "Tamil", "Telugu", "Marathi",
  "Gujarati", "Punjabi", "Kannada", "Malayalam", "Urdu", "Odia", "Assamese",
];

export default function VoicePage() {
  const [transcript, setTranscript] = useState("Hey Nova open daily notes");
  const [alwaysListening, setAlwaysListening] = useState(true);
  const [resultSummary, setResultSummary] = useState(
    "Awaiting voice utterance — detects language automatically and verifies speaker voiceprint when enabled."
  );

  return (
    <WorkspaceShell routeId="voice">
      {({ token, setStatusNote }) => (
        <div className="space-y-5">
          <GlassCard>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <Mic className="h-6 w-6 text-sky-400" />
                <div>
                  <h2 className="text-lg font-bold">Continuous Multilingual Voice Intelligence</h2>
                  <p className="text-xs text-slate-400">
                    Wake word &bull; Far-field noise filtering &bull; Interruptible TTS &bull; Voice Identity
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setAlwaysListening((v) => !v)}
                className={`rounded-xl px-3 py-1.5 text-xs font-semibold ${
                  alwaysListening
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                    : "bg-white/5 text-slate-300 border border-white/10"
                }`}
              >
                Always-Listening: {alwaysListening ? "ENABLED" : "PUSH-TO-TALK"}
              </button>
            </div>

            <div className="mt-4 flex flex-col gap-3 sm:flex-row">
              <label htmlFor="voice-transcript" className="sr-only">Voice Transcript</label>
              <input
                id="voice-transcript"
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                className="flex-1 rounded-xl border border-white/10 bg-black/25 px-3 py-2 text-xs outline-none focus:border-sky-500"
              />
              <button
                type="button"
                onClick={async () => {
                  if (token) {
                    const res = await ecosystemApi.voiceProcess(token, {
                      transcript,
                      always_listening: alwaysListening,
                      noise_db: 18,
                    });
                    setResultSummary(
                      `Lang=${res.language_name} | Intent=${res.detected_intent} | Confidence=${res.confidence} | Access=${res.access_level} | Reply: ${res.reply_text}`
                    );
                    setStatusNote(`Processed voice command in ${res.language_name}.`);
                  } else {
                    setResultSummary(`Previewed command "${transcript}" with wake-word & language routing.`);
                  }
                }}
                className="inline-flex items-center gap-1.5 rounded-xl bg-aspirant-gradient px-4 py-2 text-xs font-semibold text-white"
              >
                <Volume2 className="h-3.5 w-3.5" /> Process Utterance
              </button>
            </div>
            <p className="mt-3 rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-sky-300">
              {resultSummary}
            </p>
          </GlassCard>

          <div className="grid gap-4 md:grid-cols-2">
            <GlassCard>
              <h3 className="text-sm font-bold text-sky-400">13 Supported Indic &amp; Global Languages</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {SUPPORTED_LANGUAGES.map((lang) => (
                  <span
                    key={lang}
                    className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-xs"
                  >
                    {lang}
                  </span>
                ))}
              </div>
            </GlassCard>
            <GlassCard>
              <div className="flex items-center gap-2 text-violet-400">
                <Shield className="h-4 w-4" />
                <h3 className="text-sm font-bold">Speaker Recognition + Password Fallback</h3>
              </div>
              <p className="mt-2 text-xs text-slate-400">
                Supports voice enrollment, cosine confidence scoring, restricted guest access on unrecognized speakers, and mandatory password/JWT verification when modifying trusted voice profiles.
              </p>
            </GlassCard>
          </div>
        </div>
      )}
    </WorkspaceShell>
  );
}
