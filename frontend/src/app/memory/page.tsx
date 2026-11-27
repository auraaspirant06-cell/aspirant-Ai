"use client";

import React, { useState } from "react";
import { Database, RefreshCw, Sparkles } from "lucide-react";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi } from "@/lib/api";

export default function MemoryPage() {
  const [memoryQuery, setMemoryQuery] = useState("");
  const [smartProfileNote, setSmartProfileNote] = useState(
    "Tracks user preferences, conversation context, frequently used actions, workflows, language & device preferences."
  );
  const [memoryResults, setMemoryResults] = useState<
    Array<{ id: string; content: string; layer: string; score: number }>
  >([
    {
      id: "demo-1",
      content: "User prefers concise dark-theme dashboards and Gemini-primary voice responses.",
      layer: "preference",
      score: 0.96,
    },
    {
      id: "demo-2",
      content: "NOVA wake-word pipeline connects Windows WinRT OCR with Multi-Agent dispatch.",
      layer: "knowledge",
      score: 0.91,
    },
  ]);

  return (
    <WorkspaceShell routeId="memory">
      {({ token, setStatusNote }) => (
        <GlassCard>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-sky-500 dark:text-sky-400" />
              <h2 className="text-lg font-bold">Smart Memory &amp; Hybrid RAG Explorer</h2>
            </div>
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center gap-1 text-xs text-violet-600 dark:text-violet-400">
                <Sparkles className="h-3.5 w-3.5" /> Qdrant + Chroma + Encrypted SQL
              </span>
              <button
                type="button"
                onClick={async () => {
                  if (token) {
                    const prof = await ecosystemApi.smartMemoryProfile(token);
                    setSmartProfileNote(
                      `Language=${prof.language_preference} | Frequent actions=${JSON.stringify(prof.frequent_actions)}`
                    );
                    setStatusNote("Loaded persistent smart memory profile.");
                  }
                }}
                className="surface-card min-h-[36px] rounded-lg px-3 py-1 text-xs font-semibold hover:border-sky-500"
              >
                Inspect Smart Profile
              </button>
            </div>
          </div>

          <p className="surface-card mt-3 rounded-xl p-2.5 text-xs text-adaptive-body">
            {smartProfileNote}
          </p>

          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!memoryQuery.trim()) return;
              if (token) {
                const res = await ecosystemApi.searchMemory(token, memoryQuery.trim());
                setMemoryResults(res.results);
                setStatusNote(`Found ${res.results.length} matching memories.`);
                return;
              }
              setMemoryResults((prev) =>
                prev.filter((m) =>
                  m.content.toLowerCase().includes(memoryQuery.toLowerCase())
                )
              );
            }}
            className="mt-4 flex gap-2"
          >
            <label htmlFor="memory-search" className="sr-only">
              Search Semantic Memory
            </label>
            <input
              id="memory-search"
              value={memoryQuery}
              onChange={(e) => setMemoryQuery(e.target.value)}
              placeholder="Search memories, preferences, or ingested documents..."
              className="input-surface flex-1 rounded-xl px-3 py-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            />
            <button
              type="submit"
              className="inline-flex min-h-[40px] items-center gap-1.5 rounded-xl bg-aspirant-gradient px-4 py-2 text-xs font-semibold text-white"
            >
              <RefreshCw className="h-3.5 w-3.5" /> Search
            </button>
          </form>
          <div className="mt-4 space-y-2">
            {memoryResults.map((m) => (
              <div key={m.id} className="surface-card rounded-xl p-3 text-xs">
                <div className="flex items-center justify-between text-[11px] font-semibold text-sky-600 dark:text-sky-400">
                  <span>Layer: {m.layer}</span>
                  <span>Score: {m.score}</span>
                </div>
                <p className="mt-1 text-adaptive-body">{m.content}</p>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </WorkspaceShell>
  );
}
