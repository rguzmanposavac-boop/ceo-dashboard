"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { api } from "@/lib/api";

// ─── Types ──────────────────────────────────────────────────────────────────

type Timeframe = "1D" | "5D" | "15D" | "1M" | "6M" | "1Y" | "5Y";

interface PriceBar {
  ts: string;
  close: number;
  volume: number | null;
}

// ─── Constants ──────────────────────────────────────────────────────────────

const TIMEFRAMES: Timeframe[] = ["1D", "5D", "15D", "1M", "6M", "1Y", "5Y"];

const DAY_MS  = 86_400_000;
const WEEK_MS = 7 * DAY_MS;
const MON_MS  = 30 * DAY_MS;

// ─── Helpers ────────────────────────────────────────────────────────────────

function fmtTs(ts: string, tf: Timeframe): string {
  const d = new Date(ts);
  if (tf === "1D")
    return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  if (tf === "5D")
    return (
      d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
      " " +
      d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })
    );
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: tf === "5Y" ? "2-digit" : undefined,
  });
}

function fmtVol(v: number): string {
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return String(v);
}

/** Binary search — largest price whose ts ≤ targetMs. */
function priceAtOrBefore(data: PriceBar[], targetMs: number): number | null {
  let lo = 0, hi = data.length - 1, result: number | null = null;
  while (lo <= hi) {
    const mid = (lo + hi) >>> 1;
    const t = new Date(data[mid].ts).getTime();
    if (t <= targetMs) {
      result = data[mid].close;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return result;
}

function pctChange(from: number | null, to: number): string | null {
  if (!from || from === 0) return null;
  const v = ((to - from) / from) * 100;
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function chgColor(s: string | null): string {
  if (!s) return "#7090b0";
  return s.startsWith("-") ? "#ff5e5e" : "#3de88a";
}

// ─── Custom Tooltip ──────────────────────────────────────────────────────────

interface TooltipInnerProps {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string }>;
  label?: string;
  data: PriceBar[];
  tf: Timeframe;
}

function PriceTooltip({ active, payload, label, data, tf }: TooltipInnerProps) {
  if (!active || !payload?.length || !label) return null;

  const close  = payload.find((p) => p.dataKey === "close")?.value;
  const volume = payload.find((p) => p.dataKey === "volume")?.value;
  if (close == null) return null;

  const hovMs  = new Date(label).getTime();
  const ref1d  = priceAtOrBefore(data, hovMs - DAY_MS);
  const ref1w  = priceAtOrBefore(data, hovMs - WEEK_MS);
  const ref1m  = priceAtOrBefore(data, hovMs - MON_MS);

  const chg1d = pctChange(ref1d, close);
  const chg1w = pctChange(ref1w, close);
  const chg1m = pctChange(ref1m, close);

  // For 1D view the entire dataset is intraday — 1W/1M refs won't exist
  const showWeek  = ref1w !== null;
  const showMonth = ref1m !== null;

  return (
    <div
      style={{
        background: "#111e35",
        border: "1px solid #1e3050",
        borderRadius: 6,
        padding: "8px 12px",
        fontSize: 11,
        lineHeight: 1.75,
        minWidth: 130,
      }}
    >
      <div style={{ color: "#7090b0", marginBottom: 2 }}>{fmtTs(label, tf)}</div>
      <div style={{ fontFamily: "monospace", fontWeight: 700, fontSize: 14, color: "#e0e6f0" }}>
        ${close.toFixed(2)}
      </div>
      {volume != null && (
        <div style={{ color: "#7090b0" }}>Vol: {fmtVol(volume)}</div>
      )}
      {(chg1d || showWeek || showMonth) && (
        <div
          style={{
            marginTop: 6,
            paddingTop: 6,
            borderTop: "1px solid #1e3050",
          }}
        >
          {chg1d && (
            <div>
              <span style={{ color: "#7090b0" }}>1D&nbsp;</span>
              <span style={{ color: chgColor(chg1d), fontFamily: "monospace" }}>{chg1d}</span>
            </div>
          )}
          {showWeek && (
            <div>
              <span style={{ color: "#7090b0" }}>1W&nbsp;</span>
              <span style={{ color: chgColor(chg1w), fontFamily: "monospace" }}>{chg1w ?? "—"}</span>
            </div>
          )}
          {showMonth && (
            <div>
              <span style={{ color: "#7090b0" }}>1M&nbsp;</span>
              <span style={{ color: chgColor(chg1m), fontFamily: "monospace" }}>{chg1m ?? "—"}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────

interface Props {
  ticker: string;
}

export function PriceChart({ ticker }: Props) {
  const [tf, setTf] = useState<Timeframe>("1M");

  const { data, isLoading } = useQuery<PriceBar[]>({
    queryKey: ["prices-tf", ticker, tf],
    queryFn:  () => api.stocks.pricesByTimeframe(ticker, tf),
    staleTime: tf === "1D" ? 60_000 : 5 * 60_000,
    enabled: !!ticker,
    retry: 1,
  });

  const chartData = useMemo(() => data ?? [], [data]);

  const firstClose = chartData[0]?.close ?? null;
  const lastClose  = chartData[chartData.length - 1]?.close ?? null;
  const lineColor  =
    lastClose != null && firstClose != null && lastClose >= firstClose
      ? "#3de88a"
      : "#ff5e5e";

  const { priceMin, priceMax, maxVolume } = useMemo(() => {
    if (!chartData.length) return { priceMin: 0, priceMax: 1, maxVolume: 1 };
    const closes  = chartData.map((d) => d.close);
    const volumes = chartData.map((d) => d.volume ?? 0);
    const mn = Math.min(...closes);
    const mx = Math.max(...closes);
    const pad = (mx - mn) * 0.05 || mx * 0.01;
    return {
      priceMin:  mn - pad,
      priceMax:  mx + pad,
      maxVolume: Math.max(...volumes, 1),
    };
  }, [chartData]);

  // Thin out X-axis ticks so labels don't overlap
  const xInterval = Math.max(1, Math.floor(chartData.length / 5));

  return (
    <div>
      {/* ── Timeframe selector ── */}
      <div className="flex gap-1 mb-3">
        {TIMEFRAMES.map((t) => (
          <button
            key={t}
            onClick={() => setTf(t)}
            className="text-xs px-2 py-0.5 rounded font-mono transition-colors"
            style={
              t === tf
                ? { background: "#5ba4ff", color: "#0a0e1a", fontWeight: 700 }
                : {
                    background: "#111e35",
                    color: "#7090b0",
                    border: "1px solid #1e3050",
                  }
            }
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Chart area ── */}
      {isLoading ? (
        <div
          className="animate-pulse rounded"
          style={{ height: 200, background: "#111e35" }}
        />
      ) : chartData.length < 2 ? (
        <div
          className="flex items-center justify-center text-text-muted text-xs"
          style={{ height: 200 }}
        >
          Sin datos
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart
            data={chartData}
            margin={{ top: 4, right: 4, bottom: 0, left: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1e3050"
              vertical={false}
            />

            <XAxis
              dataKey="ts"
              tickFormatter={(ts) => fmtTs(ts, tf)}
              interval={xInterval}
              tick={{ fontSize: 9, fill: "#7090b0" }}
              axisLine={false}
              tickLine={false}
            />

            {/* Price axis — left */}
            <YAxis
              yAxisId="price"
              domain={[priceMin, priceMax]}
              tick={{ fontSize: 9, fill: "#7090b0" }}
              tickFormatter={(v: number) => `$${v >= 100 ? v.toFixed(0) : v.toFixed(1)}`}
              axisLine={false}
              tickLine={false}
              width={44}
            />

            {/* Volume axis — right, hidden ticks; domain ×5 keeps bars at ~20% height */}
            <YAxis
              yAxisId="volume"
              orientation="right"
              domain={[0, maxVolume * 5]}
              tick={false}
              axisLine={false}
              tickLine={false}
              width={0}
            />

            <Tooltip
              content={(props) => (
                <PriceTooltip
                  active={props.active}
                  payload={props.payload as TooltipInnerProps["payload"]}
                  label={props.label as string}
                  data={chartData}
                  tf={tf}
                />
              )}
            />

            {/* Volume bars — rendered first so price line sits on top */}
            <Bar
              yAxisId="volume"
              dataKey="volume"
              fill="#5ba4ff28"
              stroke="none"
              isAnimationActive={false}
            />

            {/* Price line */}
            <Line
              yAxisId="price"
              type="monotone"
              dataKey="close"
              stroke={lineColor}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
