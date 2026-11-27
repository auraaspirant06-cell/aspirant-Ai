"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowRight, Mic, Share2, ShieldCheck } from "lucide-react";
import { AgentPipelineView } from "@/components/AgentPipelineView";
import { CommandBar } from "@/components/CommandBar";
import { GlassCard } from "@/components/GlassCard";
import { ProductSuiteGrid } from "@/components/ProductSuiteGrid";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi } from "@/lib/api";

export default function OverviewPage() {
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
          <CommandBar
            onSubmit={async (prompt) => {
              if (token) {
                const res = await ecosystemApi.executeAgents(token, {
                  objective: prompt,
                  source_app: "web",
                });
                setSelectedAgents(res.selected_agents);
                setPlanSteps(res.plan_steps);
                setStatusNote(`Dispatched multi-agent run ${res.run_id.slice(0, 8)}.`);
              } else {
                setSelectedAgents(["planning", "research", "coding", "content", "support"]);
                setPlanSteps([
                  { order: 1, agent: "planning", output: `Planned: ${prompt}` },
                  { order: 2, agent: "research", output: "Grounded against hybrid Qdrant/Chroma memory." },
                ]);
                setStatusNote("Previewed multi-agent plan (connect JWT to run against backend).");
              }
            }}
          />

          <ProductSuiteGrid />

          <div className="grid gap-4 md:grid-cols-3 text-xs">
            <Link href="/voice" className="glass-panel flex items-center justify-between rounded-2xl p-4 hover:border-sky-500/50">
              <div className="flex items-center gap-3">
                <Mic className="h-5 w-5 text-sky-400" />
                <div>
                  <p className="font-bold">Voice & Speaker ID</p>
                  <p className="text-slate-400">13 Indic languages + voice enrollment</p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-sky-400" />
            </Link>
            <Link href="/integrations" className="glass-panel flex items-center justify-between rounded-2xl p-4 hover:border-violet-500/50">
              <div className="flex items-center gap-3">
                <Share2 className="h-5 w-5 text-violet-400" />
                <div>
                  <p className="font-bold">Official Social Connectors</p>
                  <p className="text-slate-400">Telegram, YouTube, Instagram, Discord, X</p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-violet-400" />
            </Link>
            <Link href="/security" className="glass-panel flex items-center justify-between rounded-2xl p-4 hover:border-emerald-500/50">
              <div className="flex items-center gap-3">
                <ShieldCheck className="h-5 w-5 text-emerald-400" />
                <div>
                  <p className="font-bold">Security & Self-Healing</p>
                  <p className="text-slate-400">Auto-repair diagnostics & audit logs</p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-emerald-400" />
            </Link>
          </div>

          <GlassCard>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-bold tracking-wide">
                7 Collaborative Specialists — Live Shared Context
              </h2>
              <Link href="/agents" className="text-xs font-semibold text-sky-400 hover:underline">
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
