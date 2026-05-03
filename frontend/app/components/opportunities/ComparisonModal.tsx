"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Stock, Catalyst } from "@/lib/types";
import { api } from "@/lib/api";

interface ComparisonModalProps {
  open: boolean;
  left?: Stock;
  right?: Stock;
  onClose: () => void;
}

function catalystNameFor(stock?: Stock, catalystMap?: Map<number, Catalyst>) {
  if (!stock || !stock.score) return "Sin catalyst asociado";
  if (stock.score.catalyst_name) return stock.score.catalyst_name;
  if (!stock.score.catalyst_id || !catalystMap) return "Sin catalyst asociado";
  return catalystMap.get(stock.score.catalyst_id)?.name ?? "Sin catalyst asociado";
}

export function ComparisonModal({ open, left, right, onClose }: ComparisonModalProps) {
  const { data: catalysts = [] } = useQuery<Catalyst[]>({
    queryKey: ["comparison-catalysts"],
    queryFn: api.catalysts.list,
    staleTime: 5 * 60 * 1000,
  });

  const catalystMap = useMemo(() => new Map(catalysts.map((c) => [c.id, c])), [catalysts]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-[#0a0e1a99] p-4">
      <div className="w-full max-w-4xl rounded-2xl border border-[#1e3050] bg-[#0f1b30] p-5 text-sm text-text-primary shadow-2xl">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h3 className="text-lg font-semibold">Comparar acciones</h3>
            <p className="text-xs text-text-secondary">Selecciona hasta dos acciones para comparar score, catalizador e invalidadores.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-text-secondary hover:text-text-primary"
          >
            ✕
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {[left, right].map((stock, index) => (
            <div key={index} className="rounded-xl border border-[#1e3050] bg-[#111e35] p-4 min-h-[220px]">
              {stock ? (
                <>
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-bold text-text-primary">{stock.ticker}</span>
                    <span className="text-xs text-text-secondary">{stock.sector}</span>
                  </div>
                  <div className="space-y-2 text-xs">
                    <p>{stock.company}</p>
                    <p>Precio: {stock.current_price != null ? `$${stock.current_price.toFixed(2)}` : "—"}</p>
                    <p>Score: {stock.score?.final_score?.toFixed(1) ?? "—"}</p>
                    <p>Señal: {stock.score?.signal ?? "—"}</p>
                    <p>Horizonte: {stock.score?.horizon ?? "—"}</p>
                    <p>Ret. estimado: {stock.score?.expected_return_low != null ? `+${(stock.score.expected_return_low * 100).toFixed(0)}% – +${(stock.score.expected_return_high ?? 0) * 100}%` : "—"}</p>
                    <p className="truncate">Catalizador: {catalystNameFor(stock, catalystMap)}</p>
                  </div>
                </>
              ) : (
                <p className="text-text-secondary">Selecciona una acción en la tabla para agregarla a la comparación.</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
