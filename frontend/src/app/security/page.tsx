"use client";

import React, { useState } from "react";
import { Lock, Wrench } from "lucide-react";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi, type SelfHealReport } from "@/lib/api";

export default function SecurityPage() {
  const [healReport, setHealReport] = useState<SelfHealReport | null>(null);
  const [crashSummary, setCrashSummary] = useState("No unhandled crashes recorded.");

  return (
    <WorkspaceShell routeId="security">
      {({ token, setStatusNote }) => (
        <div className="space-y-5">
          <GlassCard>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Lock className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                <h2 className="text-lg font-bold">Zero-Trust Security &amp; Crash Recovery</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={async () => {
                    if (token) {
                      const logs = await ecosystemApi.crashRecoveryLogs(token);
                      setCrashSummary(`Recorded crash journal entries: ${logs.crashes.length}`);
                      setStatusNote("Inspected crash recovery journal.");
                    }
                  }}
                  className="surface-card min-h-[40px] rounded-xl px-3 py-1.5 text-xs font-semibold hover:border-sky-500"
                >
                  Check Crash Journal
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    if (token) {
                      const rep = await ecosystemApi.selfHealAudit(token, false);
                      setHealReport(rep);
                      setStatusNote(`Self-healing status: ${rep.overall_status}.`);
                    }
                  }}
                  className="inline-flex min-h-[40px] items-center gap-1.5 rounded-xl bg-aspirant-gradient px-3.5 py-1.5 text-xs font-semibold text-white"
                >
                  <Wrench className="h-3.5 w-3.5" /> Run Self-Healing Audit
                </button>
              </div>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 text-xs">
              <div className="surface-card rounded-xl p-3">
                <p className="font-semibold text-sky-600 dark:text-sky-400">
                  Authentication &amp; Tokens
                </p>
                <p className="mt-1 text-adaptive-muted">
                  Argon2id hashing + HS256 JWT + rotating Refresh Tokens + Speaker Identity Gate
                </p>
              </div>
              <div className="surface-card rounded-xl p-3">
                <p className="font-semibold text-violet-600 dark:text-violet-400">
                  Encryption At Rest
                </p>
                <p className="mt-1 text-adaptive-muted">
                  Fernet AES-HMAC field encryption for memories, notes, and social tokens
                </p>
              </div>
            </div>
            <p className="surface-card mt-3 rounded-xl p-3 text-xs text-adaptive-body">
              {crashSummary}
            </p>
            {healReport && (
              <div className="surface-card mt-4 space-y-2 rounded-xl p-3 text-xs">
                <p className="font-semibold text-emerald-600 dark:text-emerald-400">
                  Self-Healing Audit: {healReport.overall_status}
                </p>
                {healReport.checks.map((c) => (
                  <div key={c.name} className="flex justify-between text-adaptive-body">
                    <span>{c.name}</span>
                    <span className="font-semibold text-sky-600 dark:text-sky-400">{c.status}</span>
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
