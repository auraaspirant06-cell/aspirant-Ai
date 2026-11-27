"use client";

import React from "react";
import { motion } from "framer-motion";
import { CheckCircle2, Cpu } from "lucide-react";

const SPECIALISTS = [
  { role: "research", label: "Research Agent", scope: "Qdrant + Chroma RAG & comparative briefs" },
  { role: "automation", label: "Automation Agent", scope: "Windows, browser, clipboard & OCR flows" },
  { role: "coding", label: "Coding Agent", scope: "Full-stack generation, debugging & tests" },
  { role: "content", label: "Content Agent", scope: "Multilingual drafts, docs & summaries" },
  { role: "productivity", label: "Productivity Agent", scope: "Reminders, habits & schedule tuning" },
  { role: "planning", label: "Planning Agent", scope: "Goal decomposition & multi-step roadmaps" },
  { role: "support", label: "Support Agent", scope: "Diagnostics & guardrail verification" },
];

interface AgentPipelineViewProps {
  selectedAgents?: string[];
  planSteps?: Array<{ order: number; agent: string; output: string }>;
}

export function AgentPipelineView({ selectedAgents = [], planSteps = [] }: AgentPipelineViewProps) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {SPECIALISTS.map((ag, idx) => {
          const active = selectedAgents.includes(ag.role);
          return (
            <motion.div
              key={ag.role}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: idx * 0.03 }}
              className={`rounded-xl border p-3.5 transition ${
                active
                  ? "border-sky-500/60 bg-sky-500/10"
                  : "surface-card"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-sky-600 dark:text-sky-400">
                  {ag.label}
                </span>
                {active ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                ) : (
                  <Cpu className="h-3.5 w-3.5 text-adaptive-muted" />
                )}
              </div>
              <p className="mt-1.5 text-xs text-adaptive-body">{ag.scope}</p>
            </motion.div>
          );
        })}
      </div>

      {planSteps.length > 0 && (
        <div className="surface-card space-y-2 rounded-xl p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-violet-600 dark:text-violet-400">
            Collaborative Execution Trace
          </p>
          {planSteps.map((step) => (
            <div key={step.order} className="surface-card rounded-lg px-3 py-2 text-xs">
              <span className="font-bold text-sky-600 dark:text-sky-400">
                #{step.order} {step.agent.toUpperCase()}:
              </span>{" "}
              <span className="text-adaptive-body">{step.output}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
