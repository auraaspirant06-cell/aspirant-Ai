"use client";

import React from "react";
import { motion } from "framer-motion";

interface BrandLoaderProps {
  label?: string;
  size?: number;
}

export function BrandLoader({ label = "Synchronizing Aspirant AI...", size = 44 }: BrandLoaderProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="inline-flex items-center gap-3 rounded-xl px-3 py-2 surface-card"
    >
      <motion.svg
        width={size}
        height={size}
        viewBox="0 0 64 64"
        aria-hidden="true"
        className="shrink-0"
      >
        <defs>
          <linearGradient id="loaderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0EA5E9" />
            <stop offset="100%" stopColor="#8B5CF6" />
          </linearGradient>
        </defs>
        <motion.circle
          cx="32"
          cy="32"
          r="26"
          fill="none"
          stroke="url(#loaderGrad)"
          strokeWidth="3.5"
          strokeDasharray="110 54"
          strokeLinecap="round"
          animate={{ rotate: 360 }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
          style={{ originX: "32px", originY: "32px" }}
        />
        <motion.circle
          cx="32"
          cy="32"
          r="17"
          fill="none"
          stroke="#38BDF8"
          strokeWidth="2"
          strokeDasharray="44 36"
          animate={{ rotate: -360 }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "linear" }}
          style={{ originX: "32px", originY: "32px" }}
        />
        <path d="M32 18 L43 44 L38 44 L32 29 L26 44 L21 44 Z" fill="url(#loaderGrad)" />
      </motion.svg>
      <span className="text-xs font-medium text-adaptive-body">{label}</span>
    </div>
  );
}
