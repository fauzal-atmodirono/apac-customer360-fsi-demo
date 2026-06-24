"use client";

import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Cell,
  PieChart, Pie, LineChart, Line, AreaChart, Area, ScatterChart, Scatter, ZAxis, ReferenceLine,
} from "recharts";
import { Card } from "@/components/ui/card";
import { PRIMARY, SEQ } from "@/lib/colors";

const AXIS = { tick: { fontSize: 12, fill: "#64748b" }, stroke: "#cbd5e1" };
const GRID = { stroke: "#eef2f7" };

export function ChartCard({
  title, caption, children,
}: { title: string; caption?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card className="flex h-full flex-col p-5">
      <h3 className="mb-3 text-sm font-semibold tracking-tight">{title}</h3>
      <div className="flex-1">{children}</div>
      {caption && (
        <p className="mt-3 flex items-start gap-1.5 text-xs leading-relaxed text-muted-foreground [&_b]:font-semibold [&_b]:text-foreground">
          <span className="text-primary">💡</span><span>{caption}</span>
        </p>
      )}
    </Card>
  );
}

type Row = Record<string, unknown>;

function pivot(rows: Row[], index: string, series: string, value: string) {
  const out = new Map<string, Row>();
  const keys = new Set<string>();
  for (const r of rows) {
    const k = String(r[index]);
    const s = String(r[series]);
    keys.add(s);
    if (!out.has(k)) out.set(k, { [index]: r[index] });
    (out.get(k) as Row)[s] = Number(r[value] ?? 0);
  }
  return { data: Array.from(out.values()), series: Array.from(keys) };
}

export function VBars({ data, xKey, valueKey, color = PRIMARY, colorKey, colorMap, height = 280 }: {
  data: Row[]; xKey: string; valueKey: string; color?: string;
  colorKey?: string; colorMap?: Record<string, string>; height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
        <CartesianGrid vertical={false} {...GRID} />
        <XAxis dataKey={xKey} {...AXIS} interval={0} angle={data.length > 5 ? -20 : 0} textAnchor={data.length > 5 ? "end" : "middle"} height={data.length > 5 ? 50 : 30} />
        <YAxis {...AXIS} />
        <Tooltip />
        <Bar dataKey={valueKey} radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {data.map((d, i) => (
            <Cell key={i} fill={colorKey && colorMap ? (colorMap[String(d[colorKey])] ?? color) : color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function HBars({ data, yKey, valueKey, color = PRIMARY, height = 280 }: {
  data: Row[]; yKey: string; valueKey: string; color?: string; height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid horizontal={false} {...GRID} />
        <XAxis type="number" {...AXIS} />
        <YAxis type="category" dataKey={yKey} {...AXIS} width={90} />
        <Tooltip />
        <Bar dataKey={valueKey} fill={color} radius={[0, 4, 4, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function GroupedBars({ data, xKey, seriesKey, valueKey, colorMap, stacked, height = 280 }: {
  data: Row[]; xKey: string; seriesKey: string; valueKey: string;
  colorMap?: Record<string, string>; stacked?: boolean; height?: number;
}) {
  const { data: wide, series } = pivot(data, xKey, seriesKey, valueKey);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={wide} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
        <CartesianGrid vertical={false} {...GRID} />
        <XAxis dataKey={xKey} {...AXIS} />
        <YAxis {...AXIS} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {series.map((s, i) => (
          <Bar key={s} dataKey={s} stackId={stacked ? "a" : undefined} isAnimationActive={false}
               fill={colorMap?.[s] ?? SEQ[i % SEQ.length]} radius={stacked ? 0 : [3, 3, 0, 0]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Donut({ data, nameKey, valueKey, colorMap, height = 280 }: {
  data: Row[]; nameKey: string; valueKey: string; colorMap?: Record<string, string>; height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey={valueKey} nameKey={nameKey} innerRadius="55%" outerRadius="80%" paddingAngle={2} isAnimationActive={false}>
          {data.map((d, i) => <Cell key={i} fill={colorMap?.[String(d[nameKey])] ?? SEQ[i % SEQ.length]} />)}
        </Pie>
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function MultiLine({ data, indexKey, seriesKey, valueKey, colorMap, height = 300 }: {
  data: Row[]; indexKey: string; seriesKey: string; valueKey: string;
  colorMap?: Record<string, string>; height?: number;
}) {
  const { data: wide, series } = pivot(data, indexKey, seriesKey, valueKey);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={wide} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
        <CartesianGrid vertical={false} {...GRID} />
        <XAxis dataKey={indexKey} {...AXIS} minTickGap={40} />
        <YAxis {...AXIS} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {series.map((s, i) => (
          <Line key={s} type="monotone" dataKey={s} stroke={colorMap?.[s] ?? SEQ[i % SEQ.length]} strokeWidth={2} dot={false} isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function StackArea({ data, indexKey, seriesKey, valueKey, height = 300 }: {
  data: Row[]; indexKey: string; seriesKey: string; valueKey: string; height?: number;
}) {
  const { data: wide, series } = pivot(data, indexKey, seriesKey, valueKey);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={wide} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
        <CartesianGrid vertical={false} {...GRID} />
        <XAxis dataKey={indexKey} {...AXIS} minTickGap={40} />
        <YAxis {...AXIS} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {series.map((s, i) => (
          <Area key={s} type="monotone" dataKey={s} stackId="a" isAnimationActive={false}
                stroke={SEQ[i % SEQ.length]} fill={SEQ[i % SEQ.length]} fillOpacity={0.6} />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function Bubble({ data, xKey, yKey, sizeKey, colorKey, colorMap, xLabel, yLabel, height = 300 }: {
  data: Row[]; xKey: string; yKey: string; sizeKey?: string; colorKey: string;
  colorMap?: Record<string, string>; xLabel?: string; yLabel?: string; height?: number;
}) {
  const groups = Array.from(new Set(data.map((d) => String(d[colorKey]))));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
        <CartesianGrid {...GRID} />
        <XAxis type="number" dataKey={xKey} {...AXIS} name={xLabel ?? xKey} />
        <YAxis type="number" dataKey={yKey} {...AXIS} name={yLabel ?? yKey} />
        {sizeKey && <ZAxis type="number" dataKey={sizeKey} range={[30, 320]} />}
        <Tooltip cursor={{ strokeDasharray: "3 3" }} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {groups.map((g, i) => (
          <Scatter key={g} name={g} data={data.filter((d) => String(d[colorKey]) === g)}
                   fill={colorMap?.[g] ?? SEQ[i % SEQ.length]} fillOpacity={0.7} isAnimationActive={false} />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}

export function Histogram({ data, valueKey, bins = 20, color = PRIMARY, refLine, height = 280 }: {
  data: Row[]; valueKey: string; bins?: number; color?: string; refLine?: number; height?: number;
}) {
  const vals = data.map((d) => Number(d[valueKey] ?? 0)).filter((v) => !Number.isNaN(v));
  const min = Math.min(...vals), max = Math.max(...vals);
  const width = (max - min) / bins || 1;
  const buckets = Array.from({ length: bins }, (_, i) => ({
    x: Math.round(min + i * width), count: 0,
  }));
  for (const v of vals) {
    const idx = Math.min(bins - 1, Math.floor((v - min) / width));
    buckets[idx].count++;
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={buckets} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
        <CartesianGrid vertical={false} {...GRID} />
        <XAxis dataKey="x" {...AXIS} />
        <YAxis {...AXIS} />
        <Tooltip />
        <Bar dataKey="count" fill={color} radius={[3, 3, 0, 0]} isAnimationActive={false} />
        {refLine !== undefined && <ReferenceLine x={Math.round(refLine)} stroke="#C62828" strokeDasharray="4 4" />}
      </BarChart>
    </ResponsiveContainer>
  );
}
