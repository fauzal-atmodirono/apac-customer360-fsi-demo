"use client";

import { ChartCard, VBars, GroupedBars, Donut, MultiLine, StackArea } from "@/components/charts";
import { KpiCard } from "@/components/kpi-card";
import { DataTable } from "@/components/data-table";
import { CHURN_COLORS, SEGMENT_COLORS, CHANNEL_COLORS } from "@/lib/colors";

export type ChartSpec = {
  type: "bar" | "line" | "area" | "pie" | "kpi";
  title?: string;
  x?: string;
  y?: string[];
  label?: string;
};

type Row = Record<string, unknown>;

const KNOWN_MAPS = [CHURN_COLORS, SEGMENT_COLORS, CHANNEL_COLORS];

// Reuse a domain palette from lib/colors when the category values match one; else default.
function colorMapFor(rows: Row[], key?: string): Record<string, string> | undefined {
  if (!key) return undefined;
  const vals = rows.map((r) => String(r[key]));
  for (const m of KNOWN_MAPS) {
    if (vals.some((v) => v in m)) return m;
  }
  return undefined;
}

// Wide → long, mirroring the pattern used in app/(dashboard)/wellness/page.tsx.
function melt(rows: Row[], x: string, yCols: string[]) {
  return rows.flatMap((r) =>
    yCols.map((y) => ({ [x]: r[x], series: y, value: Number(r[y] ?? 0) })),
  );
}

function fmtNum(v: unknown) {
  const n = Number(v);
  if (v === null || v === undefined || Number.isNaN(n)) return String(v ?? "");
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function AgentChart({ spec, rows }: { spec: ChartSpec; rows: Row[] }) {
  if (!spec || !rows?.length) return null;

  const y = (spec.y ?? []).filter(Boolean);
  const x = spec.x;
  const cols = new Set(Object.keys(rows[0]));
  const hasY = y.length > 0 && y.every((c) => cols.has(c));

  if (spec.type === "kpi") {
    if (!hasY) return null;
    return (
      <div className="mt-3 max-w-[16rem]">
        <KpiCard label={spec.label ?? spec.title ?? y[0]} value={fmtNum(rows[0][y[0]])} />
      </div>
    );
  }

  const hasX = !!x && cols.has(x);
  if (!hasX || !hasY) return null;

  let chart: React.ReactNode = null;
  if (spec.type === "bar") {
    chart =
      y.length > 1 ? (
        <GroupedBars data={melt(rows, x!, y)} xKey={x!} seriesKey="series" valueKey="value" />
      ) : (
        <VBars data={rows} xKey={x!} valueKey={y[0]} colorKey={x} colorMap={colorMapFor(rows, x)} />
      );
  } else if (spec.type === "pie") {
    chart = <Donut data={rows} nameKey={x!} valueKey={y[0]} colorMap={colorMapFor(rows, x)} />;
  } else if (spec.type === "line") {
    chart = <MultiLine data={melt(rows, x!, y)} indexKey={x!} seriesKey="series" valueKey="value" />;
  } else if (spec.type === "area") {
    chart = <StackArea data={melt(rows, x!, y)} indexKey={x!} seriesKey="series" valueKey="value" />;
  }
  if (!chart) return null;

  return (
    <div className="mt-3">
      <ChartCard title={spec.title ?? ""}>{chart}</ChartCard>
    </div>
  );
}

// Renders the agent's raw result rows as a table, with columns inferred from the first row.
export function AgentTable({ rows }: { rows: Row[] }) {
  if (!rows?.length) return null;
  const columns = Object.keys(rows[0]).map((k) => ({
    key: k,
    label: k.replace(/_/g, " "),
    align: typeof rows[0][k] === "number" ? ("right" as const) : undefined,
    fmt: (v: unknown) => (typeof v === "number" ? fmtNum(v) : String(v ?? "")),
  }));
  return <DataTable title={`Data · ${rows.length} row${rows.length === 1 ? "" : "s"}`} columns={columns} rows={rows} />;
}
