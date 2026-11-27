"use client";

import React, { useState } from "react";
import { Settings } from "lucide-react";
import { GlassCard } from "@/components/GlassCard";
import { useTheme } from "@/components/ThemeProvider";
import { WorkspaceShell } from "@/components/WorkspaceShell";

export default function SettingsPage() {
  const { theme, toggleTheme } = useTheme();
  const [wakeWord, setWakeWord] = useState("Hey Baby");
  const [voiceGender, setVoiceGender] = useState("female");
  const [defaultModel, setDefaultModel] = useState("gemini-4-hydrogen");
  const [preferredLang, setPreferredLang] = useState("hi-IN");
  const [voiceAuthUnlock, setVoiceAuthUnlock] = useState(false);

  return (
    <WorkspaceShell routeId="settings">
      {({ setStatusNote }) => (
        <GlassCard>
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5 text-sky-500 dark:text-sky-400" />
            <h2 className="text-lg font-bold">Ecosystem Preferences &amp; System Settings</h2>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2 text-xs">
            <div className="surface-card space-y-3 rounded-xl p-4">
              <div>
                <label
                  htmlFor="wake-word-select"
                  className="mb-1 block font-semibold text-sky-600 dark:text-sky-400"
                >
                  Primary Wake Phrase
                </label>
                <select
                  id="wake-word-select"
                  value={wakeWord}
                  onChange={(e) => {
                    setWakeWord(e.target.value);
                    setStatusNote(`Wake phrase updated to '${e.target.value}'.`);
                  }}
                  className="select-surface w-full rounded-xl p-2 font-medium"
                >
                  <option value="Hey Baby">Hey Baby (Default)</option>
                  <option value="Hey Aspirant">Hey Aspirant</option>
                  <option value="Hey Nova">Hey Nova</option>
                  <option value="Ok Nova">Ok Nova</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="voice-gender-select"
                  className="mb-1 block font-semibold text-sky-600 dark:text-sky-400"
                >
                  Companion Voice Gender
                </label>
                <select
                  id="voice-gender-select"
                  value={voiceGender}
                  onChange={(e) => {
                    setVoiceGender(e.target.value);
                    setStatusNote(`Companion voice gender set to ${e.target.value}.`);
                  }}
                  className="select-surface w-full rounded-xl p-2 font-medium"
                >
                  <option value="female">Female (Aanya / Swara / Kore)</option>
                  <option value="male">Male (Arjun / Madhur / Puck)</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="model-select"
                  className="mb-1 block font-semibold text-sky-600 dark:text-sky-400"
                >
                  Primary AI Router Model
                </label>
                <select
                  id="model-select"
                  value={defaultModel}
                  onChange={(e) => setDefaultModel(e.target.value)}
                  className="select-surface w-full rounded-xl p-2 font-medium"
                >
                  <option value="gemini-4-hydrogen">Gemini 4 Hydrogen (Fast Coding &amp; Agentic)</option>
                  <option value="gemini-4-argon">Gemini 4 Argon (Balanced)</option>
                  <option value="gemini-4-carbon">Gemini 4 Carbon (Deep Research)</option>
                  <option value="gemini-3.8-flash">Gemini 3.8 Flash (Low Latency)</option>
                  <option value="gpt-4o-mini">OpenAI-Compatible (GPT)</option>
                  <option value="qwen2.5:latest">Ollama Local</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="lang-pref-select"
                  className="mb-1 block font-semibold text-sky-600 dark:text-sky-400"
                >
                  Remembered Spoken Language
                </label>
                <select
                  id="lang-pref-select"
                  value={preferredLang}
                  onChange={(e) => setPreferredLang(e.target.value)}
                  className="select-surface w-full rounded-xl p-2 font-medium"
                >
                  <option value="auto">Auto-Detect (14 Languages + Code-Switching)</option>
                  <option value="hinglish">Hinglish (Natural Indian Code-Switch)</option>
                  <option value="hi">Hindi (हिन्दी)</option>
                  <option value="en">English (Indian Accent Preset)</option>
                  <option value="bn">Bengali (বাংলা)</option>
                  <option value="ta">Tamil (தமிழ்)</option>
                </select>
              </div>
            </div>

            <div className="surface-card space-y-4 rounded-xl p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-semibold text-violet-600 dark:text-violet-400">
                    Appearance Theme
                  </p>
                  <p className="text-adaptive-muted">Current: {theme}</p>
                </div>
                <button
                  type="button"
                  onClick={toggleTheme}
                  className="surface-card min-h-[40px] rounded-xl px-3.5 py-2 font-semibold hover:border-sky-500"
                >
                  Toggle Theme
                </button>
              </div>
              <div className="flex items-center justify-between gap-3 pt-2">
                <div>
                  <p className="font-semibold text-violet-600 dark:text-violet-400">
                    Voice Identity Unlock
                  </p>
                  <p className="text-adaptive-muted">
                    Requires password fallback for profile changes
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setVoiceAuthUnlock((v) => !v);
                    setStatusNote("Updated voice identity unlock setting.");
                  }}
                  className="min-h-[40px] rounded-xl bg-aspirant-gradient px-3.5 py-2 font-semibold text-white"
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
