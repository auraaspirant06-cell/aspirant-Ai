"use client";

import React, { useState } from "react";
import { AgentPipelineView } from "@/components/AgentPipelineView";
import { CommandBar } from "@/components/CommandBar";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi } from "@/lib/api";

export default function AgentsPage() {
  const [selectedAgents, setSelectedAgents] = useState<string[]>([
    "planning",
    "research",
    "coding",
    "support",
  ]);
  const [planSteps, setPlanSteps] = useState<
    Array<{ order: number; agent: string; output: string }>
  >([]);
  const [reflectionSummary, setReflectionSummary] = useState(
    "Long-chain reasoning, self-reflection, and feedback adaptation ready."
  );

  return (
    <WorkspaceShell routeId="agents">
      {({ token, setStatusNote }) => (
        <div className="space-y-5">
          <CommandBar
            placeholder="Run deep reasoning, multi-agent planning & self-reflection..."
            onSubmit={async (objective) => {
              if (token) {
                const res = await ecosystemApi.reasonDeep(token, { objective });
                setReflectionSummary(
                  `Intent=${res.intent} (confidence ${res.confidence}) | Self-reflection passed=${res.reflection.passed} | ${res.final_answer}`
                );
                const run = await ecosystemApi.executeAgents(token, {
                  objective,
                  source_app: "web",
                });
                setSelectedAgents(run.selected_agents);
                setPlanSteps(run.plan_steps);
                setStatusNote(`Reasoning + 7-agent run ${run.run_id.slice(0, 8)} completed.`);
              } else {
                setSelectedAgents(["planning", "research", "coding", "support"]);
                setPlanSteps([
                  { order: 1, agent: "planning", output: `Intent parsed for "${objective}"` },
                  { order: 2, agent: "support", output: "Self-reflection & error check passed." },
                ]);
              }
            }}
          />
          <GlassCard>
            <h2 className="mb-2 text-lg font-bold">Multi-Agent Reasoning &amp; Self-Reflection</h2>
            <p className="mb-4 rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-violet-300">
              {reflectionSummary}
            </p>
            <AgentPipelineView selectedAgents={selectedAgents} planSteps={planSteps} />
          </GlassCard>
        </div>
      )}
    </WorkspaceShell>
  );
}
