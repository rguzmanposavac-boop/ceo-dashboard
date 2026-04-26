"use client";

import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { ScoreBreakdown as ScoreBreakdownType } from "@/lib/types";

interface Props {
  score: ScoreBreakdownType;
}

export function ScoreBreakdown({ score }: Props) {
  const data = [
    { axis: "Sector/Régimen", value: score.sector_score ?? 0 },
    { axis: "Fundamentals",   value: score.base_score ?? 0 },
    { axis: "CEO",            value: score.ceo_score ?? 0 },
    { axis: "ROIC/WACC",      value: score.roic_wacc_score ?? 0 },
    { axis: "Catalizador",    value: score.catalyst_total ?? 0 },
  ];

  return (
    <ResponsiveContainer width="100%" height={220}>
      <RadarChart data={data}>
        <PolarGrid stroke="#1e3050" />
        <PolarAngleAxis
          dataKey="axis"
          tick={{ fill: "#7090b0", fontSize: 11 }}
        />
        <Radar
          name="Score"
          dataKey="value"
          stroke="#5ba4ff"
          fill="#5ba4ff"
          fillOpacity={0.18}
          strokeWidth={1.5}
        />
        <Tooltip
          contentStyle={{ background: "#111e35", border: "1px solid #1e3050", fontSize: 11 }}
          formatter={(v: number) => [v.toFixed(1), "Score"]}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
