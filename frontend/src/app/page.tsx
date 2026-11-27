"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowRight, Mic, Share2, ShieldCheck } from "lucide-react";
import { AgentPipelineView } from "@/components/AgentPipelineView";
import { BrandLoader } from "@/components/BrandLoader";
import { CommandBar } from "@/components/CommandBar";
import { GlassCard } from "@/components/GlassCard";
import { ProductSuiteGrid } from "@/components/ProductSuiteGrid";
import { Robot3D, type RobotState } from "@/components/Robot3D";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi } from "@/lib/api";

export default function OverviewPage() {
  const [busy, setBusy] = useState(false);
  const [robotState, setRobotState] = useState<RobotState>("IDLE");
  const [robotNote, setRobotNote] = useState("Standing by — say 'Hey Baby' or dispatch an AI task.");
  const [speechAmp, setSpeechAmp] = useState(0);
  const [selectedAgents, setSelectedAgents] = useState<string[]>([
    "planning",
    "research",
    "coding",
    "support",
  ]);
  const [planSteps, setPlanSteps] = useState<
    Array<{ order: number; agent: string; output: string }>
  >([
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

  return (
    <WorkspaceShell routeId="overview">
      {({ token, setStatusNote }) => (
        <div className="space-y-5">
          <div className="grid gap-5 lg:grid-cols-12">
            <div className="space-y-4 lg:col-span-7">
              <CommandBar
                busy={busy}
                onSubmit={async (prompt) => {
                  setBusy(true);
                  const lower = prompt.toLowerCase();
                  setRobotState(lower.includes("code") || lower.includes("build") ? "CODING" : "THINKING");
                  setRobotNote(`Executing: "${prompt.slice(0, 56)}"`);
                  try {
                    if (token) {
                      const res = await ecosystemApi.executeAgents(token, {
                        objective: prompt,
                        source_app: "web",
                      });
                      setSelectedAgents(res.selected_agents);
                      setPlanSteps(res.plan_steps);
                      setRobotState("SPEAKING");
                      setSpeechAmp(0.8);
                      setRobotNote(`Completed multi-agent run ${res.run_id.slice(0, 8)}.`);
                      setStatusNote(`Dispatched multi-agent run ${res.run_id.slice(0, 8)}.`);
                    } else {
                      setSelectedAgents(["planning", "research", "coding", "content", "support"]);
                      setPlanSteps([
                        { order: 1, agent: "planning", output: `Planned: ${prompt}` },
                        { order: 2, agent: "research", output: "Grounded against hybrid Qdrant/Chroma memory." },
                      ]);
                      setRobotState("SUCCESS");
                      setSpeechAmp(0.45);
                      setRobotNote("Preview orchestration complete.");
                      setStatusNote("Previewed multi-agent plan (connect JWT to run against backend).");
                    }
                  } catch (err) {
                    setRobotState("ERROR");
                    setSpeechAmp(0);
                    setRobotNote(err instanceof Error ? err.message : "Task failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              />
              {busy && <BrandLoader label="Orchestrating collaborative Aspirant AI agents..." />}
              <ProductSuiteGrid />
            </div>

            <div className="lg:col-span-5">
              <Robot3D
                state={robotState}
                statusText={robotNote}
                speechAmplitude={speechAmp}
                wakePhrase="Hey Baby"
                voiceGender="female"
                onStateSelect={(next) => {
                  setRobotState(next);
                  setSpeechAmp(next === "SPEAKING" ? 0.78 : next === "LISTENING" ? 0.3 : 0);
                  setRobotNote(`Interactive mode: ${next}`);
                }}
              />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3 text-xs">
            <Link
              href="/voice"
              className="glass-panel flex min-h-[68px] items-center justify-between rounded-2xl p-4 hover:border-sky-500/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            >
              <div className="flex items-center gap-3">
                <Mic className="h-5 w-5 text-sky-500 dark:text-sky-400" />
                <div>
                  <p className="font-bold">Voice &amp; Speaker ID</p>
                  <p className="text-adaptive-muted">14 Indic &amp; Hinglish + Mic Health</p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-sky-500 dark:text-sky-400" />
            </Link>
            <Link
              href="/integrations"
              className="glass-panel flex min-h-[68px] items-center justify-between rounded-2xl p-4 hover:border-violet-500/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            >
              <div className="flex items-center gap-3">
                <Share2 className="h-5 w-5 text-violet-600 dark:text-violet-400" />
                <div>
                  <p className="font-bold">Official Social Connectors</p>
                  <p className="text-adaptive-muted">Telegram, YouTube, Instagram, Discord, X</p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-violet-600 dark:text-violet-400" />
            </Link>
            <Link
              href="/security"
              className="glass-panel flex min-h-[68px] items-center justify-between rounded-2xl p-4 hover:border-emerald-500/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            >
              <div className="flex items-center gap-3">
                <ShieldCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                <div>
                  <p className="font-bold">Security &amp; Self-Healing</p>
                  <p className="text-adaptive-muted">Auto-repair, crash logs &amp; audit</p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            </Link>
          </div>

          <GlassCard>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-bold tracking-wide">
                7 Collaborative Specialists — Live Shared Context
              </h2>
              <Link
                href="/agents"
                className="text-xs font-semibold text-sky-600 hover:underline dark:text-sky-400"
              >
                Open Deep Reasoning Console
              </Link>
            </div>
            <AgentPipelineView selectedAgents={selectedAgents} planSteps={planSteps} />
          </GlassCard>
        </div>
      )}
    </WorkspaceShell>
  );
}
