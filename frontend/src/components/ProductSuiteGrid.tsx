"use client";

import React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { BrandMark } from "./BrandMark";
import { GlassCard } from "./GlassCard";

const PRODUCTS: Array<{
  id: "nova" | "mj" | "max";
  href: "/nova" | "/mj" | "/max";
  title: string;
  role: string;
  accent: string;
  bullets: string[];
}> = [
  {
    id: "nova",
    href: "/nova",
    title: "NOVA",
    role: "Windows Desktop Autonomous Operator",
    accent: "text-sky-600 dark:text-sky-400 border-sky-500/40",
    bullets: [
      'Wake word "Hey Nova" + continuous natural voice',
      "Windows integration, clipboard & WinRT OCR intelligence",
      "Command guardrails & multi-agent desktop execution",
    ],
  },
  {
    id: "mj",
    href: "/mj",
    title: "MJ",
    role: "Human-Like Deep Intelligence",
    accent: "text-violet-600 dark:text-violet-400 border-violet-500/40",
    bullets: [
      "Persistent cross-device memory & user profiling",
      "Document RAG synthesis, email & calendar awareness",
      "Deep research mode & autonomous milestone planning",
    ],
  },
  {
    id: "max",
    href: "/max",
    title: "MAX",
    role: "Android-First Mobile Companion",
    accent: "text-indigo-600 dark:text-indigo-400 border-indigo-500/40",
    bullets: [
      "Offline SQLite queue with delta sync reconciliation",
      "Voice commands, habit streaks & smart reminders",
      "AI note summarization & push notifications",
    ],
  },
];

export function ProductSuiteGrid() {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {PRODUCTS.map((p, idx) => (
        <GlassCard key={p.id} delay={idx * 0.05} className="flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <BrandMark product={p.id} size={42} />
                <div className="min-w-0">
                  <h2 className="text-base font-bold tracking-wide">{p.title}</h2>
                  <p className="text-xs text-adaptive-muted">{p.role}</p>
                </div>
              </div>
              <Link
                href={p.href}
                aria-label={`Open ${p.title} workspace`}
                className={`inline-flex min-h-[36px] min-w-[36px] items-center justify-center rounded-lg border p-1.5 transition hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${p.accent}`}
              >
                <ArrowUpRight className="h-4 w-4" />
              </Link>
            </div>
            <ul className="mt-4 space-y-2 text-xs text-adaptive-body">
              {p.bullets.map((b) => (
                <li key={b} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-500" />
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          </div>
          <Link
            href={p.href}
            className="surface-card mt-5 flex min-h-[40px] w-full items-center justify-center rounded-xl text-xs font-semibold transition hover:border-sky-500/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            Launch {p.title} Console
          </Link>
        </GlassCard>
      ))}
    </div>
  );
}
