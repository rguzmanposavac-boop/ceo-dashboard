"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { InvalidatorAlert as InvalidatorAlertType } from "@/lib/types";

export function InvalidatorAlert({ onSelectTicker }: { onSelectTicker?: (ticker: string) => void }) {
  const [invalidators, setInvalidators] = useState<InvalidatorAlertType[]>([]);
  const [status, setStatus] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => api.invalidators.check(),
    onSuccess: (data) => {
      setInvalidators(data.invalidators);
      setStatus(`Invalidadores activos: ${data.invalidators.length}`);
    },
    onError: () => setStatus("No se pudo obtener invalidadores"),
  });

  return (
    <section className="rounded-lg border border-[#1e3050] bg-[#0f1b30] p-4">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div>
          <p className="text-xs uppercase tracking-widest text-text-secondary">Invalidadores</p>
          <p className="text-sm text-text-primary">Monitorea señales de salida y riesgos vigentes.</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setStatus("Buscando invalidadores…");
            mutation.mutate();
          }}
          className="text-xs px-3 py-1 rounded"
          style={{ background: "#5ba4ff18", border: "1px solid #5ba4ff44", color: "#5ba4ff" }}
        >
          Chequear ahora
        </button>
      </div>

      {status && <p className="text-xs text-text-secondary mb-3">{status}</p>}

      {invalidators.length === 0 ? (
        <p className="text-xs text-text-secondary">No se han identificado invalidadores recientes.</p>
      ) : (
        <div className="space-y-2">
          {invalidators.slice(0, 4).map((item) => (
            <button
              key={`${item.ticker}-${item.key}`}
              type="button"
              onClick={() => onSelectTicker?.(item.ticker)}
              className="w-full text-left rounded border border-[#1e3050] px-3 py-2 text-xs transition"
              style={{ background: "#111e35", color: "#e0e6f0" }}
            >
              <div className="font-semibold text-text-primary">{item.ticker}</div>
              <div className="text-text-secondary">{item.description}</div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
