"use client";

import { useQuery } from "@tanstack/react-query";
import { LineChart, Line, ResponsiveContainer, Tooltip } from "recharts";
import { api } from "@/lib/api";
import type { PricePoint } from "@/lib/types";

interface Props {
  ticker: string;
  height?: number;
}

export function MiniChart({ ticker, height = 48 }: Props) {
  const { data, isLoading } = useQuery<PricePoint[]>({
    queryKey: ["price-history", ticker],
    queryFn: () => api.stocks.priceHistory(ticker, 63),
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return <div className="animate-pulse bg-border rounded" style={{ height }} />;
  }

  if (!data || data.length < 2) {
    return <div className="text-text-muted text-xs text-center" style={{ height }}>sin datos</div>;
  }

  // Price history comes newest-first; reverse for chart
  const chartData = [...data].reverse().map((p) => ({ v: p.close_price }));
  const first = chartData[0].v;
  const last = chartData[chartData.length - 1].v;
  const color = last >= first ? "#3de88a" : "#ff5e5e";

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData}>
        <Line
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
        <Tooltip
          contentStyle={{ background: "#111e35", border: "1px solid #1e3050", fontSize: 11 }}
          labelFormatter={() => ""}
          formatter={(v: number) => [`$${v.toFixed(2)}`, ticker]}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
