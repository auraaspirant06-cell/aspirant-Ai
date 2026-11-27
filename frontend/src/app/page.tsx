"use client";

import React, { useState } from "react";
import { Activity, Database, KeyRound, Lock, RefreshCw, Sparkles } from "lucide-react";
import { AgentPipelineView } from "@/components/AgentPipelineView";
import { BrandMark } from "@/components/BrandMark";
import { CommandBar } from "@/components/CommandBar";
import { GlassCard } from "@/components/GlassCard";
import { ProductSuiteGrid } from "@/components/ProductSuiteGrid";
import { Sidebar, type WorkspaceTab } from "@/components/Sidebar";
import { ecosystemApi } from "@/lib/api";

export default function EcosystemConsolePage() {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview");
  const [token, setToken] = useState<string>("");
  const [email, setEmail] = useState("founder@aspirant.ai");
  const [password, setPassword] = useState("StrongPassword!2026");
  const [statusNote, setStatusNote] = useState("Ready — connect to FastAPI backend or run interactive simulation.");
  const [busy, setBusy] = useState(false);

  const [selectedAgents, setSelectedAgents] = useState<string[]>([
    "planning",
    "research",
    "coding",
    "support",
  ]);
  const [planSteps, setPlanSteps] = useState<Array<{ order: number; agent: string; output: string }>>([
    {
      order: 1,
      agent: "planning",
      output: "Synchronized cross-device context across NOVA, MJ, and MAX.",
    },
    {
      order: 2,
      agent: "research",
      output: "Indexed knowledge chunks in Qdrant + Chroma vector memory stores.",
    },
  ]);

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

  const [clipboardSample, setClipboardSample] = useState("def analyze_pipeline():\n    return True");
  const [clipboardKind, setClipboardKind] = useState("code");

  const handleAuthenticate = async () => {
    setBusy(true);
    try {
      let auth;
      try {
        auth = await ecosystemApi.login({ email, password });
      } catch {
        auth = await ecosystemApi.register({ email, password, full_name: "Aspirant Owner" });
      }
      setToken(auth.access_token);
      setStatusNote(`Authenticated as ${auth.user.email} (JWT session active).`);
    } catch (err) {
      setStatusNote(
        `Offline UI preview mode (${err instanceof Error ? err.message : "backend unreachable"}).`
      );
    } finally {
      setBusy(false);
    }
  };

  const handleCommandDispatch = async (prompt: string) => {
    setBusy(true);
    try {
      if (token) {
        const res = await ecosystemApi.executeAgents(token, {
          objective: prompt,
          source_app: activeTab === "mj" ? "mj" : activeTab === "max" ? "max" : "nova",
        });
        setSelectedAgents(res.selected_agents);
        setPlanSteps(res.plan_steps);
        setStatusNote(`Executed multi-agent run ${res.run_id.slice(0, 8)} via FastAPI backend.`);
      } else {
        setSelectedAgents(["planning", "research", "coding", "content", "support"]);
        setPlanSteps([
          { order: 1, agent: "planning", output: `Decomposed objective: "${prompt}"` },
          { order: 2, agent: "research", output: "Retrieved semantic recall from Qdrant/Chroma." },
          { order: 3, agent: "coding", output: "Prepared modular execution artifacts." },
          { order: 4, agent: "content", output: "Formatted multilingual response ready for voice/UI." },
        ]);
        setStatusNote("Simulated multi-agent workflow (sign in with live backend to persist to PostgreSQL/SQLite).");
      }
    } finally {
      setBusy(false);
    }
  };

  const handleMemorySearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!memoryQuery.trim()) return;
    if (token) {
      try {
        const res = await ecosystemApi.searchMemory(token, memoryQuery.trim());
        setMemoryResults(res.results);
        return;
      } catch {
        // Fallback below
      }
    }
    setMemoryResults((prev) =>
      prev.filter((m) => m.content.toLowerCase().includes(memoryQuery.toLowerCase()))
    );
  };

  const handleClipboardInspect = async () => {
    if (token) {
      try {
        const res = await ecosystemApi.novaClipboard(token, clipboardSample);
        setClipboardKind(res.kind);
        setStatusNote(`NOVA classified clipboard as '${res.kind}'.`);
        return;
      } catch {
        // Offline heuristic fallback
      }
    }
    setClipboardKind(clipboardSample.includes("def ") ? "code" : "plain_text");
    setStatusNote("Analyzed clipboard sample in local preview.");
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-5 p-4 md:p-6 lg:flex-row">
      <Sidebar activeTab={activeTab} onSelect={setActiveTab} />

      <main className="flex-1 space-y-5">
        <header className="glass-panel flex flex-col justify-between gap-4 rounded-2xl p-5 sm:flex-row sm:items-center">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-sky-400">
              <Activity className="h-3.5 w-3.5" />
              <span>Unified Personal AI Operating System</span>
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight">
              Aspirant AI <span className="gradient-text">{activeTab.toUpperCase()}</span> Workspace
            </h1>
            <p className="mt-1 text-xs text-slate-400">{statusNote}</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <label htmlFor="auth-email" className="sr-only">Email</label>
            <input
              id="auth-email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-1.5 text-xs outline-none focus:border-sky-500"
            />
            <label htmlFor="auth-pass" className="sr-only">Password</label>
            <input
              id="auth-pass"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-32 rounded-xl border border-white/10 bg-black/20 px-3 py-1.5 text-xs outline-none focus:border-sky-500"
            />
            <button
              type="button"
              onClick={handleAuthenticate}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-xl bg-aspirant-gradient px-3.5 py-1.5 text-xs font-semibold text-white"
            >
              <KeyRound className="h-3.5 w-3.5" />
              <span>{token ? "Connected" : "Connect JWT"}</span>
            </button>
          </div>
        </header>

        <CommandBar onSubmit={handleCommandDispatch} busy={busy} />

        {activeTab === "overview" && (
          <>
            <ProductSuiteGrid onNavigate={setActiveTab} />
            <GlassCard>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-bold tracking-wide">
                  7 Collaborative Specialists — Live Shared Context
                </h2>
                <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400">
                  Gemini + GPT-Compat + Qdrant/Chroma
                </span>
              </div>
              <AgentPipelineView selectedAgents={selectedAgents} planSteps={planSteps} />
            </GlassCard>
          </>
        )}

        {activeTab === "nova" && (
          <GlassCard>
            <div className="flex items-center gap-3">
              <BrandMark product="nova" size={44} />
              <div>
                <h2 className="text-lg font-bold">NOVA Desktop Control & Automation</h2>
                <p className="text-xs text-slate-400">
                  Wake word &ldquo;Hey Nova&rdquo; • Clipboard Intelligence • WinRT OCR • Safe Terminal Guard
                </p>
              </div>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="space-y-2 rounded-xl border border-white/10 p-4">
                <label htmlFor="clipboard-box" className="text-xs font-semibold text-sky-400">
                  Clipboard Intelligence Inspector ({clipboardKind})
                </label>
                <textarea
                  id="clipboard-box"
                  rows={4}
                  value={clipboardSample}
                  onChange={(e) => setClipboardSample(e.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-black/25 p-3 font-mono text-xs outline-none focus:border-sky-500"
                />
                <button
                  type="button"
                  onClick={handleClipboardInspect}
                  className="rounded-xl bg-sky-500/20 px-3 py-1.5 text-xs font-semibold text-sky-300 hover:bg-sky-500/30"
                >
                  Classify & Suggest NOVA Actions
                </button>
              </div>
              <div className="space-y-2 rounded-xl border border-white/10 p-4 text-xs text-slate-300">
                <p className="font-semibold text-violet-400">Desktop Capabilities Active</p>
                <p>• Global Hotkey Bridge: Ctrl+Shift+N & Tray Quick Menu</p>
                <p>• Isolated Edge Playwright Automation + Policy Approval Queue</p>
                <p>• Gemini 3.8 Live Female Natural Voice + 18+ Indian Languages</p>
                <p>• Emergency STOP Hardware Kill-Switch Integration</p>
              </div>
            </div>
          </GlassCard>
        )}

        {activeTab === "mj" && (
          <GlassCard>
            <div className="flex items-center gap-3">
              <BrandMark product="mj" size={44} />
              <div>
                <h2 className="text-lg font-bold">MJ Human-Like Intelligence</h2>
                <p className="text-xs text-slate-400">
                  Persistent Memory • Goal Milestones • Deep Research • Email & Calendar Intelligence
                </p>
              </div>
            </div>
            <div className="mt-4">
              <AgentPipelineView selectedAgents={["research", "planning", "content", "productivity"]} planSteps={planSteps} />
            </div>
          </GlassCard>
        )}

        {activeTab === "max" && (
          <GlassCard>
            <div className="flex items-center gap-3">
              <BrandMark product="max" size={44} />
              <div>
                <h2 className="text-lg font-bold">MAX Android-First Mobile Companion</h2>
                <p className="text-xs text-slate-400">
                  Offline SQLite Store • Real-Time Delta Sync • Habit Streaks • Smart Reminders & Notes
                </p>
              </div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3 text-xs">
              <div className="rounded-xl border border-white/10 p-3">
                <p className="font-semibold text-sky-400">Daily Focus Plan</p>
                <p className="mt-1 text-slate-400">Syncs goals & top 5 due reminders to mobile home widget.</p>
              </div>
              <div className="rounded-xl border border-white/10 p-3">
                <p className="font-semibold text-violet-400">Offline-First Queue</p>
                <p className="mt-1 text-slate-400">Captures voice notes & habit check-ins without connectivity.</p>
              </div>
              <div className="rounded-xl border border-white/10 p-3">
                <p className="font-semibold text-emerald-400">Celery Push Alerts</p>
                <p className="mt-1 text-slate-400">Dispatches timely mobile notifications across time zones.</p>
              </div>
            </div>
          </GlassCard>
        )}

        {activeTab === "agents" && (
          <GlassCard>
            <h2 className="mb-3 text-lg font-bold">Multi-Agent Orchestration Graph</h2>
            <AgentPipelineView selectedAgents={selectedAgents} planSteps={planSteps} />
          </GlassCard>
        )}

        {activeTab === "memory" && (
          <GlassCard>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Database className="h-5 w-5 text-sky-400" />
                <h2 className="text-lg font-bold">Semantic Memory & Hybrid RAG Explorer</h2>
              </div>
              <span className="inline-flex items-center gap-1 text-xs text-violet-400">
                <Sparkles className="h-3.5 w-3.5" /> Qdrant + Chroma + Encrypted SQL
              </span>
            </div>
            <form onSubmit={handleMemorySearch} className="mt-4 flex gap-2">
              <label htmlFor="memory-search" className="sr-only">Search Semantic Memory</label>
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
                <div key={m.id} className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs">
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

        {activeTab === "security" && (
          <GlassCard>
            <div className="flex items-center gap-2">
              <Lock className="h-5 w-5 text-emerald-400" />
              <h2 className="text-lg font-bold">Zero-Trust Security & Audit Architecture</h2>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 text-xs">
              <div className="rounded-xl border border-white/10 p-3">
                <p className="font-semibold text-sky-400">Authentication & Tokens</p>
                <p className="mt-1 text-slate-400">Argon2id hashing + HS256 JWT + rotating single-use Refresh Tokens</p>
              </div>
              <div className="rounded-xl border border-white/10 p-3">
                <p className="font-semibold text-violet-400">Encryption At Rest</p>
                <p className="mt-1 text-slate-400">Fernet AES-HMAC field encryption for memories & private notes</p>
              </div>
              <div className="rounded-xl border border-white/10 p-3">
                <p className="font-semibold text-emerald-400">Transport & Edge Guard</p>
                <p className="mt-1 text-slate-400">HTTPS HSTS enforcement, sliding-window rate limits, CSP/CORS headers</p>
              </div>
              <div className="rounded-xl border border-white/10 p-3">
                <p className="font-semibold text-amber-400">PII-Redacted Audit Trail</p>
                <p className="mt-1 text-slate-400">Every auth, agent, and command check logged without raw secrets</p>
              </div>
            </div>
          </GlassCard>
        )}
      </main>
    </div>
  );
}
