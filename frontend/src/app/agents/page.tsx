"use client";

import React, { useState } from "react";
import { Bug, Code2, Server } from "lucide-react";
import { AgentPipelineView } from "@/components/AgentPipelineView";
import { CommandBar } from "@/components/CommandBar";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi } from "@/lib/api";

const STACK_OPTIONS = [
  "FastAPI", "Python", "Django", "Flask", "Go", "Rust", "Java", "Kotlin",
  "C#", "Node.js", "TypeScript", "React", "Next.js", "Vue", "Angular", "PHP", "Laravel",
  "SQL", "Swift", "Dart", "Shell", "PowerShell",
];

const DEVOPS_PLATFORMS = [
  "Azure", "Ubuntu VPS", "Docker", "Kubernetes", "AWS", "Google Cloud", "Oracle Cloud",
  "DigitalOcean", "Hetzner", "Nginx", "Cloudflare",
];

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
    "Long-chain reasoning, self-reflection, and cross-session feedback learning ready."
  );

  const [projectName, setProjectName] = useState("aspirant-fastapi-app");
  const [stack, setStack] = useState("FastAPI");
  const [platform, setPlatform] = useState("Ubuntu VPS");
  const [errorInput, setErrorInput] = useState("ModuleNotFoundError: No module named 'fastapi'");
  const [engineeringOutput, setEngineeringOutput] = useState(
    "Aspirant AI Project Generator (17 stacks / 8 deliverables), DevOps Agent (9 platforms), and 5-Step Debugger ready for Harsh / Boss."
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
            <p className="surface-card mb-4 rounded-xl p-3 text-xs text-violet-700 dark:text-violet-300">
              {reflectionSummary}
            </p>
            <AgentPipelineView selectedAgents={selectedAgents} planSteps={planSteps} />
          </GlassCard>

          <GlassCard>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-sky-500 dark:text-sky-400">
                <Code2 className="h-5 w-5" />
                <h3 className="text-sm font-bold">
                  Project Generator, DevOps Automation &amp; Debugging Assistant
                </h3>
              </div>
              <span className="text-[11px] text-adaptive-muted">Futuristic Glass Studio</span>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div>
                <label htmlFor="proj-name-input" className="text-[11px] text-adaptive-muted">
                  Project Name
                </label>
                <input
                  id="proj-name-input"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  className="input-surface mt-1 w-full rounded-xl px-3 py-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                />
              </div>

              <div>
                <label htmlFor="proj-stack-select" className="text-[11px] text-adaptive-muted">
                  Stack (22 Supported)
                </label>
                <select
                  id="proj-stack-select"
                  value={stack}
                  onChange={(e) => setStack(e.target.value)}
                  className="select-surface mt-1 min-h-[36px] w-full rounded-xl px-3 py-1.5 text-xs font-semibold outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                >
                  {STACK_OPTIONS.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="devops-platform-select" className="text-[11px] text-adaptive-muted">
                  DevOps Platform (11 Supported)
                </label>
                <select
                  id="devops-platform-select"
                  value={platform}
                  onChange={(e) => setPlatform(e.target.value)}
                  className="select-surface mt-1 min-h-[36px] w-full rounded-xl px-3 py-1.5 text-xs font-semibold outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                >
                  {DEVOPS_PLATFORMS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={async () => {
                  if (token) {
                    const pack = await ecosystemApi.generateProject(token, { project_name: projectName, stack });
                    setEngineeringOutput(
                      `Deliverables (${pack.deliverables.length}): ${pack.deliverables.join(", ")}\n\n${pack.folder_structure}`
                    );
                    setStatusNote(`Generated ${pack.stack} 8-deliverable blueprint.`);
                  } else {
                    setEngineeringOutput(
                      `Preview: Ready to generate 8 deliverables for ${projectName} (${stack}). Connect JWT to invoke API.`
                    );
                  }
                }}
                className="inline-flex min-h-[36px] items-center gap-1.5 rounded-xl bg-aspirant-gradient px-3 py-1.5 text-xs font-semibold text-white"
              >
                <Code2 className="h-3.5 w-3.5" /> Generate 8-Deliverable Project
              </button>

              <button
                type="button"
                onClick={async () => {
                  if (token) {
                    const plan = await ecosystemApi.devopsPlan(token, { app_name: projectName, platform });
                    setEngineeringOutput(
                      `${plan.message}\nStatus=${plan.status} | ConfirmationRequired=${plan.confirmation_required}\n\n${plan.reverse_proxy_configuration}`
                    );
                    setStatusNote(`Prepared ${plan.platform} DevOps plan (awaiting execution confirmation).`);
                  } else {
                    setEngineeringOutput(
                      `Preview: Deployment guide for ${platform} prepared cleanly (deployment NOT claimed complete until execution is confirmed).`
                    );
                  }
                }}
                className="surface-card inline-flex min-h-[36px] items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold hover:border-sky-500"
              >
                <Server className="h-3.5 w-3.5" /> Prepare DevOps Plan
              </button>
            </div>

            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
              <label htmlFor="debug-log-input" className="sr-only">Error Log</label>
              <input
                id="debug-log-input"
                value={errorInput}
                onChange={(e) => setErrorInput(e.target.value)}
                className="input-surface flex-1 rounded-xl px-3 py-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
              />
              <button
                type="button"
                onClick={async () => {
                  if (token) {
                    const dbg = await ecosystemApi.debugLogs(token, { error_log: errorInput });
                    setEngineeringOutput(
                      `Root Cause: ${dbg.root_cause}\nIssue: ${dbg.issue_explanation}\nFix: ${dbg.fix}\nPrevention: ${dbg.prevention_methods.join("; ")}`
                    );
                    setStatusNote("Completed 5-step debugging analysis.");
                  } else {
                    setEngineeringOutput(`Preview Debug Analysis: Inspect traceback root cause for "${errorInput}".`);
                  }
                }}
                className="surface-card inline-flex min-h-[36px] items-center justify-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold hover:border-amber-500"
              >
                <Bug className="h-3.5 w-3.5" /> Analyze Error Log
              </button>
            </div>

            <pre className="surface-card mt-3 whitespace-pre-wrap rounded-xl p-3 text-xs text-sky-700 dark:text-sky-300">
              {engineeringOutput}
            </pre>
          </GlassCard>
        </div>
      )}
    </WorkspaceShell>
  );
}
