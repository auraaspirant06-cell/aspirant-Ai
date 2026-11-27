"use client";

import React, { useState } from "react";
import { Database, RefreshCw, Sparkles } from "lucide-react";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi } from "@/lib/api";

export default function MemoryPage() {
  const [memoryQuery, setMemoryQuery] = useState("");
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
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-sky-400" />
              <h2 className="text-lg font-bold">Semantic Memory &amp; Hybrid RAG Explorer</h2>
            </div>
            <span className="inline-flex items-center gap-1 text-xs text-violet-400">
              <Sparkles className="h-3.5 w-3.5" /> Qdrant + Chroma + Encrypted SQL
            </span>
          </div>
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
              className="flex-1 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs outline-none focus:border-sky-500"
            />
            <button
              type="submit"
              className="inline-flex items-center gap-1.5 rounded-xl bg-aspirant-gradient px-4 py-2 text-xs font-semibold text-white"
            >
              <RefreshCw className="h-3.5 w-3.5" /> Search
            </button>
          </form>
          <div className="mt-4 space-y-2">
            {memoryResults.map((m) => (
              <div
                key={m.id}
                className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs"
              >
                <div className="flex items-center justify-between text-[11px] text-sky-400">
                  <span>Layer: {m.layer}</span>
                  <span>Score: {m.score}</span>
                </div>
                <p className="mt-1 text-slate-200">{m.content}</p>
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </WorkspaceShell>
  );
}
