"use client";

import React, { useState } from "react";
import { Loader2, Send, ShieldAlert } from "lucide-react";

interface CommandBarProps {
  onSubmit: (prompt: string) => Promise<void>;
  placeholder?: string;
  busy?: boolean;
}

export function CommandBar({
  onSubmit,
  placeholder = "Ask NOVA, MJ, MAX, or dispatch the 7 collaborative agents...",
  busy = false,
}: CommandBarProps) {
  const [value, setValue] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim() || busy) return;
    const text = value.trim();
    setValue("");
    await onSubmit(text);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="glass-panel flex items-center gap-3 rounded-2xl px-4 py-3 shadow-glow"
    >
      <ShieldAlert className="h-4 w-4 shrink-0 text-sky-400" aria-hidden="true" />
      <label htmlFor="ecosystem-command-input" className="sr-only">
        Command Input
      </label>
      <input
        id="ecosystem-command-input"
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400"
      />
      <button
        type="submit"
        disabled={busy || !value.trim()}
        className="inline-flex items-center gap-2 rounded-xl bg-aspirant-gradient px-4 py-2 text-xs font-semibold text-white transition hover:opacity-95 disabled:opacity-40"
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
        <span>Dispatch</span>
      </button>
    </form>
  );
}
