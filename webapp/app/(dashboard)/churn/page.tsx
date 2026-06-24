"use client";

import Link from "next/link";
import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, Donut, Bubble, Histogram, GroupedBars } from "@/components/charts";
import { DataTable } from "@/components/data-table";
import { CHURN_COLORS } from "@/lib/colors";
import { money, num } from "@/lib/format";

type Churn = {
  drivers: { band: string; customers: number; avg_atm: number; avg_savings: number; pct_dormant: number; savings_at_risk: number }[];
  bands: { band: string; customers: number }[];
  scatter: { customer_id: string; band: string; churn_risk_score: number; atm: number; savings: number }[];
  scoreDist: { churn_risk_score: number; band: string }[];
  byAge: { age_band: string; band: string; customers: number }[];
  list: { customer_id: string; full_name: string; band: string; churn_risk_score: number; atm: number; savings: number }[];
};

export default function ChurnPage() {
  const { data, error, isLoading } = useApi<Churn>("churn");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const total = data.drivers.reduce((s, d) => s + num(d.customers), 0);
  const atRisk = data.drivers.filter((d) => ["HIGH", "MEDIUM"].includes(d.band));
  const nRisk = atRisk.reduce((s, d) => s + num(d.customers), 0);
  const dollars = atRisk.reduce((s, d) => s + num(d.savings_at_risk), 0);
  const low = data.drivers.find((d) => d.band === "LOW");

  return (
    <div className="space-y-5">
      <PageHeader title="Churn risk" subtitle="Weighted on ATM cash-flight intensity, thin savings, and dormant card activity." />
      <KpiRow>
        <KpiCard label="At-risk customers" value={String(nRisk)} sub={`${((nRisk / total) * 100).toFixed(0)}% of base`} accent="danger" />
        <KpiCard label="Savings at risk" value={money(dollars)} />
        <KpiCard label="Avg ATM (at-risk)" value={`${(atRisk.reduce((s, d) => s + num(d.avg_atm), 0) / (atRisk.length || 1)).toFixed(1)}/mo`} />
        <KpiCard label="HIGH band" value={String(num(data.drivers.find((d) => d.band === "HIGH")?.customers))} accent="danger" />
      </KpiRow>

      <Insight tone="warning">
        <b>{nRisk}</b> customers ({((nRisk / total) * 100).toFixed(0)}%) are HIGH/MEDIUM churn risk, holding <b>{money(dollars)}</b> in
        savings. At-risk customers average more ATM withdrawals than the <b>{num(low?.avg_atm).toFixed(1)}/mo</b> of low-risk customers.
      </Insight>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Risk bands"
          caption={<><b>{((1 - nRisk / total) * 100).toFixed(0)}%</b> low-risk; the rest are the watchlist to act on before defection.</>}>
          <Donut data={data.bands} nameKey="band" valueKey="customers" colorMap={CHURN_COLORS} />
        </ChartCard>
        <ChartCard title="ATM cash-flight vs savings"
          caption={<>At-risk customers (red/amber) sit bottom-right — thin savings drained by frequent ATM withdrawals.</>}>
          <Bubble data={data.scatter} xKey="atm" yKey="savings" sizeKey="churn_risk_score" colorKey="band" colorMap={CHURN_COLORS} xLabel="ATM (30d)" yLabel="savings" />
        </ChartCard>
        <ChartCard title="Churn-score distribution"
          caption={<>Scores cluster low; the tail above ~35 is the active watchlist as ATM/dormancy signals build.</>}>
          <Histogram data={data.scoreDist} valueKey="churn_risk_score" color="#C62828" />
        </ChartCard>
        <ChartCard title="Risk band by age"
          caption={<>Tailor retention messaging (rates, fee waivers) to the most at-risk age cohorts.</>}>
          <GroupedBars data={data.byAge} xKey="age_band" seriesKey="band" valueKey="customers" colorMap={CHURN_COLORS} />
        </ChartCard>
      </div>

      <DataTable title="Retention target list (HIGH / MEDIUM)" rows={data.list}
        columns={[
          { key: "customer_id", label: "CIF", fmt: (v) => <Link href={`/customers/${v}`} className="text-primary hover:underline">{String(v)}</Link> },
          { key: "full_name", label: "Name" },
          { key: "band", label: "Band" },
          { key: "churn_risk_score", label: "Score", align: "right", fmt: (v) => num(v as number).toFixed(0) },
          { key: "atm", label: "ATM 30d", align: "right" },
          { key: "savings", label: "Savings", align: "right", fmt: (v) => money(v as number) },
        ]} />
    </div>
  );
}
