"use client";

import React, { useState } from "react";
import { Settings } from "lucide-react";
import { GlassCard } from "@/components/GlassCard";
import { useTheme } from "@/components/ThemeProvider";
import { WorkspaceShell } from "@/components/WorkspaceShell";

export default function SettingsPage() {
  const { theme, toggleTheme } = useTheme();
  const [wakeWord, setWakeWord] = useState("Hey Nova");
  const [defaultModel, setDefaultModel] = useState("gemini-4-argon");
  const [voiceAuthUnlock, setVoiceAuthUnlock] = useState(false);

  return (
    <WorkspaceShell routeId="settings">
      {({ setStatusNote }) => (
        <GlassCard>
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5 text-sky-400" />
            <h2 className="text-lg font-bold">Ecosystem Preferences &amp; System Settings</h2>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2 text-xs">
            <div className="space-y-2 rounded-xl border border-white/10 p-4">
              <label htmlFor="wake-word-select" className="block font-semibold text-sky-400">
                Primary Wake Phrase
              </label>
              <select
                id="wake-word-select"
                value={wakeWord}
                onChange={(e) => setWakeWord(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-black/30 p-2"
              >
                <option value="Hey Nova">Hey Nova</option>
                <option value="Hey Aspirant">Hey Aspirant</option>
                <option value="Ok Nova">Ok Nova</option>
              </select>

              <label htmlFor="model-select" className="mt-3 block font-semibold text-sky-400">
                Primary AI Router Model
              </label>
              <select
                id="model-select"
                value={defaultModel}
                onChange={(e) => setDefaultModel(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-black/30 p-2"
              >
                <option value="gemini-4-argon">Gemini 4 Argon (Balanced)</option>
                <option value="gemini-4-carbon">Gemini 4 Carbon (Deep Research)</option>
                <option value="gpt-4o-mini">OpenAI-Compatible (GPT)</option>
                <option value="qwen2.5:latest">Ollama Local</option>
              </select>
            </div>

            <div className="space-y-3 rounded-xl border border-white/10 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold text-violet-400">Appearance Theme</p>
                  <p className="text-slate-400">Current: {theme}</p>
                </div>
                <button
                  type="button"
                  onClick={toggleTheme}
                  className="rounded-xl border border-white/10 px-3 py-1.5 font-semibold hover:border-sky-500"
                >
                  Toggle Theme
                </button>
              </div>
              <div className="flex items-center justify-between pt-2">
                <div>
                  <p className="font-semibold text-violet-400">Voice Identity Unlock</p>
                  <p className="text-slate-400">Requires password fallback for profile changes</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setVoiceAuthUnlock((v) => !v);
                    setStatusNote("Updated local voice identity unlock preference.");
                  }}
                  className="rounded-xl bg-aspirant-gradient px-3 py-1.5 font-semibold text-white"
                >
                  {voiceAuthUnlock ? "Enabled" : "Disabled"}
                </button>
              </div>
            </div>
          </div>
        </GlassCard>
      )}
    </WorkspaceShell>
  );
}
