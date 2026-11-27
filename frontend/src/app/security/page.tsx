"use client";

import React, { useState } from "react";
import { Lock, Wrench } from "lucide-react";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi, type SelfHealReport } from "@/lib/api";

export default function SecurityPage() {
  const [healReport, setHealReport] = useState<SelfHealReport | null>(null);

  return (
    <WorkspaceShell routeId="security">
      {({ token, setStatusNote }) => (
        <div className="space-y-5">
          <GlassCard>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Lock className="h-5 w-5 text-emerald-400" />
                <h2 className="text-lg font-bold">Zero-Trust Security &amp; Audit Architecture</h2>
              </div>
              <button
                type="button"
                onClick={async () => {
                  if (token) {
                    const rep = await ecosystemApi.selfHealAudit(token, false);
                    setHealReport(rep);
                    setStatusNote(`Self-healing status: ${rep.overall_status}.`);
                  }
                }}
                className="inline-flex items-center gap-1.5 rounded-xl bg-aspirant-gradient px-3.5 py-1.5 text-xs font-semibold text-white"
              >
                <Wrench className="h-3.5 w-3.5" /> Run Self-Healing Audit
              </button>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 text-xs">
              <div className="rounded-xl border border-white/10 p-3">
                <p className="font-semibold text-sky-400">Authentication &amp; Tokens</p>
                <p className="mt-1 text-slate-400">
                  Argon2id hashing + HS256 JWT + rotating Refresh Tokens + Speaker Identity Gate
                </p>
              </div>
              <div className="rounded-xl border border-white/10 p-3">
                <p className="font-semibold text-violet-400">Encryption At Rest</p>
                <p className="mt-1 text-slate-400">
                  Fernet AES-HMAC field encryption for memories, notes, and social tokens
                </p>
              </div>
            </div>
            {healReport && (
              <div className="mt-4 space-y-2 rounded-xl border border-white/10 bg-black/25 p-3 text-xs">
                <p className="font-semibold text-emerald-400">
                  Self-Healing Audit: {healReport.overall_status}
                </p>
                {healReport.checks.map((c) => (
                  <div key={c.name} className="flex justify-between text-slate-300">
                    <span>{c.name}</span>
                    <span className="text-sky-400">{c.status}</span>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        </div>
      )}
    </WorkspaceShell>
  );
}
