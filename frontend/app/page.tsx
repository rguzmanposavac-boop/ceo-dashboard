"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Stock } from "@/lib/types";
import { useDashboardStore } from "@/stores/dashboardStore";
import { RegimeHeader } from "@/app/components/layout/RegimeHeader";
import { OpportunityRadar } from "@/app/components/opportunities/OpportunityRadar";
import { StockDetail } from "@/app/components/detail/StockDetail";
import { CatalystMonitor } from "@/app/components/catalysts/CatalystMonitor";
import { FooterStats } from "@/app/components/layout/FooterStats";

export default function DashboardPage() {
  const { selectedTicker, selectTicker } = useDashboardStore();

  const { data: stocks = [], isLoading } = useQuery<Stock[]>({
    queryKey: ["stocks"],
    queryFn: () => api.stocks.list(),
    refetchInterval: 5 * 60 * 1000,
  });

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "#0a0e1a" }}>
      {/* Zone 1 — Regime Header */}
      <RegimeHeader stocks={stocks} />

      {/* Main content */}
      <main className="flex-1 max-w-screen-2xl mx-auto w-full px-4 py-4 flex flex-col gap-4">

        {/* Zone 2 + Zone 3 */}
        <div className="flex gap-4 items-start">
          {/* Zone 2 — Opportunity Radar */}
          <div className={selectedTicker ? "flex-1 min-w-0" : "w-full"}>
            {isLoading ? (
              <div
                className="rounded-lg p-8 text-center text-text-secondary animate-pulse"
                style={{ background: "#0f1b30", border: "1px solid #1e3050" }}
              >
                Cargando acciones…
              </div>
            ) : (
              <OpportunityRadar
                stocks={stocks}
                onSelect={(t) => selectTicker(selectedTicker === t ? null : t)}
                selectedTicker={selectedTicker}
              />
            )}
          </div>

          {/* Zone 3 — Stock Detail panel */}
          {selectedTicker && (
            <div className="w-80 lg:w-96 shrink-0 sticky top-16 max-h-[calc(100vh-5rem)] overflow-y-auto">
              <StockDetail ticker={selectedTicker} onClose={() => selectTicker(null)} />
            </div>
          )}
        </div>

        {/* Zone 4 — Catalyst Monitor */}
        <CatalystMonitor />
      </main>

      {/* Zone 5 — Footer with backtesting stats */}
      <FooterStats />
    </div>
  );
}
