"use client";

import React from "react";
import { ArrowUpRight } from "lucide-react";
import { BrandMark } from "./BrandMark";
import { GlassCard } from "./GlassCard";
import type { WorkspaceTab } from "./Sidebar";

interface ProductSuiteGridProps {
  onNavigate: (tab: WorkspaceTab) => void;
}

const PRODUCTS: Array<{
  id: "nova" | "mj" | "max";
  title: string;
  role: string;
  accent: string;
  bullets: string[];
}> = [
  {
    id: "nova",
    title: "NOVA",
    role: "Windows Desktop Autonomous Operator",
    accent: "text-sky-400 border-sky-500/30",
    bullets: [
      'Wake word "Hey Nova" + continuous natural voice',
      "System, browser, clipboard & WinRT OCR intelligence",
      "Command guardrails & multi-agent desktop execution",
    ],
  },
  {
    id: "mj",
    title: "MJ",
    role: "Human-Like Deep Intelligence",
    accent: "text-violet-400 border-violet-500/30",
    bullets: [
      "Persistent cross-device memory & user profiling",
      "Document RAG synthesis, email & calendar awareness",
      "Deep research mode & autonomous milestone planning",
    ],
  },
  {
    id: "max",
    title: "MAX",
    role: "Android-First Mobile Companion",
    accent: "text-indigo-400 border-indigo-500/30",
    bullets: [
      "Offline SQLite queue with delta sync reconciliation",
      "Voice commands, habit streaks & smart reminders",
      "AI note summarization & push notifications",
    ],
  },
];

export function ProductSuiteGrid({ onNavigate }: ProductSuiteGridProps) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {PRODUCTS.map((p, idx) => (
        <GlassCard key={p.id} delay={idx * 0.06} className="flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <BrandMark product={p.id} size={42} />
                <div>
                  <h2 className="text-base font-bold tracking-wide">{p.title}</h2>
                  <p className="text-xs text-slate-400">{p.role}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onNavigate(p.id)}
                aria-label={`Open ${p.title} workspace`}
                className={`rounded-lg border p-1.5 transition hover:scale-105 ${p.accent}`}
              >
                <ArrowUpRight className="h-4 w-4" />
              </button>
            </div>
            <ul className="mt-4 space-y-2 text-xs text-slate-500 dark:text-slate-300">
              {p.bullets.map((b) => (
                <li key={b} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400" />
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          </div>
          <button
            type="button"
            onClick={() => onNavigate(p.id)}
            className="mt-5 w-full rounded-xl border border-white/10 bg-white/5 py-2 text-xs font-semibold transition hover:border-sky-500/50 hover:text-sky-400"
          >
            Launch {p.title} Console
          </button>
        </GlassCard>
      ))}
    </div>
  );
}
