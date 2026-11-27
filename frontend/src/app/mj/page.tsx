"use client";

import React, { useState } from "react";
import { AgentPipelineView } from "@/components/AgentPipelineView";
import { BrandMark } from "@/components/BrandMark";
import { CommandBar } from "@/components/CommandBar";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi } from "@/lib/api";

export default function MjPage() {
  const [reply, setReply] = useState(
    "MJ is ready with persistent cross-session memory, document RAG, and goal planning."
  );

  return (
    <WorkspaceShell routeId="mj">
      {({ token, setStatusNote }) => (
        <div className="space-y-5">
          <CommandBar
            placeholder="Ask MJ to plan milestones, draft an email, or synthesize documents..."
            onSubmit={async (msg) => {
              if (token) {
                const res = await ecosystemApi.mjChat(token, msg);
                setReply(res.reply);
                setStatusNote(`MJ replied using ${res.provider}/${res.model}.`);
              } else {
                setReply(`MJ simulated companion response for: "${msg}"`);
                setStatusNote("MJ offline preview updated.");
              }
            }}
          />
          <GlassCard>
            <div className="flex items-center gap-3">
              <BrandMark product="mj" size={44} />
              <div>
                <h2 className="text-lg font-bold">MJ Human-Like Intelligence</h2>
                <p className="text-xs text-slate-400">
                  Persistent Memory • Goal Milestones • Deep Research • Email &amp; Calendar Intelligence
                </p>
              </div>
            </div>
            <p className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs text-slate-200">
              {reply}
            </p>
            <div className="mt-4">
              <AgentPipelineView selectedAgents={["research", "planning", "content", "productivity"]} />
            </div>
          </GlassCard>
        </div>
      )}
    </WorkspaceShell>
  );
}
