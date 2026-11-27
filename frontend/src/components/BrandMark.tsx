"use client";

import React from "react";

interface BrandMarkProps {
  product?: "aspirant" | "nova" | "mj" | "max";
  size?: number;
}

const SRC_MAP: Record<NonNullable<BrandMarkProps["product"]>, string> = {
  aspirant: "/brand/mark-transparent.png",
  nova: "/brand/nova-mark.png",
  mj: "/brand/mj-mark.png",
  max: "/brand/max-mark.png",
};

export function BrandMark({ product = "aspirant", size = 36 }: BrandMarkProps) {
  return (
    <img
      src={SRC_MAP[product]}
      alt={`Aspirant AI ${product.toUpperCase()} emblem`}
      width={size}
      height={size}
      className="rounded-xl object-contain shrink-0"
    />
  );
}
