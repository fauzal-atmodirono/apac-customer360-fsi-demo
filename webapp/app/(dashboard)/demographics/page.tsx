"use client";

import dynamic from "next/dynamic";
import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { ChartCard, HBars, VBars } from "@/components/charts";
import { Card } from "@/components/ui/card";
import { money, num } from "@/lib/format";

const MalaysiaMap = dynamic(() => import("@/components/malaysia-map"), { ssr: false });

type Demo = {
  regions: { region: string; customers: number; total_savings: number; avg_ips: number }[];
  income: { income_band: string; customers: number; avg_savings: number; avg_income: number }[];
  tenure: { tenure_band: string; customers: number; avg_savings: number; avg_churn: number }[];
};

const INCOME_ORDER = ["LOW", "MID", "HIGH", "VERY_HIGH"];

export default function DemographicsPage() {
  const { data, error, isLoading } = useApi<Demo>("demographics");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const top = [...data.regions].sort((a, b) => b.customers - a.customers)[0];
  const richReg = [...data.regions].sort((a, b) => b.total_savings - a.total_savings)[0];
  const hiIncome = data.income.filter((r) => ["HIGH", "VERY_HIGH"].includes(r.income_band))
    .reduce((s, r) => s + num(r.customers), 0);
  const income = [...data.income].sort((a, b) => INCOME_ORDER.indexOf(a.income_band) - INCOME_ORDER.indexOf(b.income_band));
  const worstTenure = [...data.tenure].sort((a, b) => b.avg_churn - a.avg_churn)[0];

  return (
    <div className="space-y-5">
      <PageHeader title="Customer demographics" subtitle="Region, income tier, and tenure — for geographic targeting and lifecycle programs." />
      <Insight>
        <b>{top.region}</b> is the largest market ({top.customers} customers, {money(top.total_savings)} savings).
        Customers span <b>{data.regions.length}</b> regions and <b>{data.income.length}</b> income tiers.
      </Insight>

      <Card className="p-5">
        <h3 className="mb-3 text-sm font-semibold tracking-tight">Customer footprint across Malaysia</h3>
        <MalaysiaMap regions={data.regions} />
        <p className="mt-3 text-xs text-muted-foreground">
          💡 Bubble size = customers. The book is anchored in the <b className="text-foreground">Klang Valley</b> and
          Peninsular Malaysia; East Malaysia metros (Kota Kinabalu, Kuching) are lighter-touch — candidates for a
          digital-first acquisition play.
        </p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Customers by region"
          caption={<>Concentrated in <b>{top.region}</b> and a few metros — focus branch staffing there, test digital elsewhere.</>}>
          <HBars data={[...data.regions].sort((a, b) => a.customers - b.customers)} yKey="region" valueKey="customers" />
        </ChartCard>
        <ChartCard title="Savings by region"
          caption={<><b>{richReg.region}</b> holds the most savings ({money(richReg.total_savings)}) — the priority for wealth & deposit products.</>}>
          <VBars data={[...data.regions].sort((a, b) => b.total_savings - a.total_savings)} xKey="region" valueKey="total_savings" />
        </ChartCard>
        <ChartCard title="Income-band distribution"
          caption={<><b>{hiIncome}</b> customers fall in HIGH / VERY_HIGH tiers — the affluent base for premium cards & advisory.</>}>
          <VBars data={income} xKey="income_band" valueKey="customers" />
        </ChartCard>
        <ChartCard title="Tenure cohorts (customers)"
          caption={<>The <b>{worstTenure.tenure_band}</b> cohort shows the highest avg churn score ({num(worstTenure.avg_churn).toFixed(0)}) — prioritize loyalty nudges there.</>}>
          <VBars data={data.tenure} xKey="tenure_band" valueKey="customers" />
        </ChartCard>
      </div>
    </div>
  );
}
