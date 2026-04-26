"use client";

import type { Invalidator } from "@/lib/types";

interface Props {
  invalidators: Invalidator[] | null | undefined;
}

export function InvalidatorsList({ invalidators }: Props) {
  if (!invalidators || invalidators.length === 0) return null;

  return (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-widest text-text-secondary mb-2">
        Invalidadores de tesis
      </h4>
      <ul className="space-y-1.5">
        {invalidators.map((inv) => (
          <li
            key={inv.key}
            className="flex gap-2 items-start text-xs rounded p-2"
            style={{ background: "#ff5e5e12", border: "1px solid #ff5e5e22" }}
          >
            <span className="text-base leading-none mt-0.5">⚠</span>
            <span className="text-text-secondary leading-relaxed">{inv.description}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
