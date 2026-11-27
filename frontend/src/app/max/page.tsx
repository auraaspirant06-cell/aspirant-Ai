"use client";

import React, { useState } from "react";
import { BrandMark } from "@/components/BrandMark";
import { GlassCard } from "@/components/GlassCard";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { ecosystemApi } from "@/lib/api";

export default function MaxPage() {
  const [planInfo, setPlanInfo] = useState(
    "Ready to load synced MAX goals, habits, and reminders."
  );

  return (
    <WorkspaceShell routeId="max">
      {({ token, setStatusNote }) => (
        <GlassCard>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <BrandMark product="max" size={44} />
              <div>
                <h2 className="text-lg font-bold">MAX Android-First Mobile Companion</h2>
                <p className="text-xs text-adaptive-muted">
                  Offline SQLite Store &bull; Real-Time Delta Sync &bull; Habit Streaks &bull; Smart Reminders &amp; Notes
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={async () => {
                if (token) {
                  const res = await ecosystemApi.maxDailyPlan(token);
                  setPlanInfo(
                    `Date ${res.date}: ${res.focus_goals.length} goals, ${res.habits.length} habits, ${res.due_reminders.length} reminders.`
                  );
                  setStatusNote("Loaded live MAX daily plan snapshot.");
                } else {
                  setPlanInfo("Offline simulation: 2 habits synced, offline SQLite queue active.");
                }
              }}
              className="min-h-[40px] rounded-xl bg-aspirant-gradient px-3.5 py-2 text-xs font-semibold text-white"
            >
              Pull Mobile Sync Snapshot
            </button>
          </div>
          <p className="surface-card mt-4 rounded-xl p-3 text-xs text-sky-600 dark:text-sky-300">
            {planInfo}
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-3 text-xs">
            <div className="surface-card rounded-xl p-3">
              <p className="font-semibold text-sky-600 dark:text-sky-400">Daily Focus Plan</p>
              <p className="mt-1 text-adaptive-muted">
                Syncs goals &amp; due reminders to Android widget.
              </p>
            </div>
            <div className="surface-card rounded-xl p-3">
              <p className="font-semibold text-violet-600 dark:text-violet-400">
                Offline-First Queue
              </p>
              <p className="mt-1 text-adaptive-muted">
                Captures voice memos &amp; habit check-ins without network.
              </p>
            </div>
            <div className="surface-card rounded-xl p-3">
              <p className="font-semibold text-emerald-600 dark:text-emerald-400">
                Celery Push Alerts
              </p>
              <p className="mt-1 text-adaptive-muted">
                Dispatches timely mobile notifications across time zones.
              </p>
            </div>
          </div>
        </GlassCard>
      )}
    </WorkspaceShell>
  );
}
