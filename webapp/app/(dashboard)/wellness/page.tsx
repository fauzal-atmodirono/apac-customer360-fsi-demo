"use client";

import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, MultiLine, Donut } from "@/components/charts";
import { money, num } from "@/lib/format";

type Cashflow = {
  bands: { band: string; customers: number }[];
  primary: { primary_bank: boolean; customers: number }[];
  trend: { month: string; inflow: number; outflow: number }[];
  kpis: { avg_wellness: number; avg_savings_rate: number; pct_primary: number; stretched: number };
  profit: { total_profit: number; avg_yield: number; earners: number };
};

const BAND_COLORS = { Healthy: "#2E7D32", Moderate: "#F9A825", Stretched: "#C62828" };

export default function WellnessPage() {
  const { data, error, isLoading } = useApi<Cashflow>("wellness");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const k = data.kpis;
  // long-format for the inflow/outflow MultiLine
  const flow = data.trend.flatMap((t) => [
    { month: t.month, series: "Inflow", value: num(t.inflow) },
    { month: t.month, series: "Outflow", value: num(t.outflow) },
  ]);
  const primaryCount = data.primary.find((p) => p.primary_bank)?.customers ?? 0;
  const last = data.trend[data.trend.length - 1];
  const monthSurplus = last ? num(last.inflow) - num(last.outflow) : 0;
  const bandTotal = data.bands.reduce((a, b) => a + num(b.customers), 0) || 1;
  const healthy = num(data.bands.find((b) => b.band === "Healthy")?.customers ?? 0);
  const stretchedW = num(data.bands.find((b) => b.band === "Stretched")?.customers ?? 0);

  return (
    <div className="space-y-5">
      <PageHeader title="Financial wellness & cashflow" subtitle="Salary inflows, spending outflows, surplus and savings behaviour — from the account ledger." />
      <KpiRow>
        <KpiCard label="Avg wellness score" value={`${num(k.avg_wellness).toFixed(0)}/100`} />
        <KpiCard label="Avg savings rate" value={`${(num(k.avg_savings_rate) * 100).toFixed(0)}%`} />
        <KpiCard label="Primary-bank share" value={`${(num(k.pct_primary) * 100).toFixed(0)}%`} />
        <KpiCard label="Financially stretched" value={num(k.stretched).toLocaleString()} accent="danger" />
      </KpiRow>

      <Insight>
        <b>{num(primaryCount).toLocaleString()}</b> customers credit their salary here (primary-bank), saving on average
        <b> {(num(k.avg_savings_rate) * 100).toFixed(0)}%</b> of inflow. <b>{num(k.stretched).toLocaleString()}</b> are
        financially stretched (outflow ≥ inflow) — targets for budgeting tools and responsible-lending journeys.
        Depositors earned <b>{money(data.profit?.total_profit)}</b> in Shariah profit (avg effective yield
        <b> {num(data.profit?.avg_yield).toFixed(1)}%</b>).
      </Insight>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Inflow vs outflow (monthly)"
          caption={<>Latest month shows a <b>{money(monthSurplus)}</b> bank-wide surplus of inflows over outflows — investable deposits to channel into term deposits & wealth-i, and a buffer to fund financing growth.</>}>
          <MultiLine data={flow} indexKey="month" seriesKey="series" valueKey="value"
            colorMap={{ Inflow: "#2E7D32", Outflow: "#C62828" }} height={300} />
        </ChartCard>
        <ChartCard title="Financial-wellness bands"
          caption={<><b>{healthy.toLocaleString()}</b> (<b>{(healthy / bandTotal * 100).toFixed(0)}%</b>) are Healthy with surplus to invest; <b>{stretchedW.toLocaleString()}</b> are stretched — a two-track play: wealth offers vs budgeting/responsible-lending support.</>}>
          <Donut data={data.bands} nameKey="band" valueKey="customers" colorMap={BAND_COLORS} />
        </ChartCard>
      </div>
    </div>
  );
}
