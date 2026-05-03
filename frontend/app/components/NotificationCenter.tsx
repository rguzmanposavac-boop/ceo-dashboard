"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Stock } from "@/lib/types";

interface Toast {
  id: string;
  title: string;
  message: string;
  type: "info" | "success" | "warning";
}

export function NotificationCenter({ stocks }: { stocks: Stock[] }) {
  const { data: invalidatorData } = useQuery({
    queryKey: ["invalidators", "summary"],
    queryFn: () => api.invalidators.check(),
    refetchInterval: 60000,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });

  const [toasts, setToasts] = useState<Toast[]>([]);
  const notifiedRef = useRef<Set<string>>(new Set());

  const strongBuys = useMemo(
    () => stocks.filter((stock) => stock.score?.signal === "COMPRA_FUERTE"),
    [stocks]
  );

  useEffect(() => {
    const next: Toast[] = [];
    strongBuys.forEach((stock) => {
      if (!notifiedRef.current.has(`strong-${stock.ticker}`)) {
        notifiedRef.current.add(`strong-${stock.ticker}`);
        next.push({
          id: `strong-${stock.ticker}`,
          title: `COMPRA FUERTE: ${stock.ticker}`,
          message: `${stock.company} mantiene una señal fuerte con score ${stock.score?.final_score?.toFixed(1)}`,
          type: "success",
        });
      }
    });

    invalidatorData?.invalidators?.forEach((inv) => {
      if (!notifiedRef.current.has(`inv-${inv.ticker}-${inv.key}`)) {
        notifiedRef.current.add(`inv-${inv.ticker}-${inv.key}`);
        next.push({
          id: `inv-${inv.ticker}-${inv.key}`,
          title: `Invalidator: ${inv.ticker}`,
          message: inv.description,
          type: "warning",
        });
      }
    });

    if (next.length > 0) {
      setToasts((current) => [...next, ...current].slice(0, 5));
      setTimeout(() => {
        setToasts((current) => current.slice(0, 4));
      }, 10_000);
    }
  }, [strongBuys, invalidatorData]);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="max-w-sm rounded-lg border px-4 py-3 shadow-xl"
          style={{
            background: toast.type === "success" ? "#213b24" : toast.type === "warning" ? "#3d231f" : "#142d45",
            borderColor: toast.type === "success" ? "#3de88a44" : toast.type === "warning" ? "#ff8c4244" : "#5ba4ff44",
            color: "#e0e6f0",
          }}
        >
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-semibold">{toast.title}</span>
            <span className="text-xs text-text-secondary">{toast.type}</span>
          </div>
          <p className="mt-1 text-xs text-text-secondary">{toast.message}</p>
        </div>
      ))}
    </div>
  );
}
