"use client";

import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, VBars, Histogram, GroupedBars, HBars } from "@/components/charts";
import { SEGMENT_COLORS } from "@/lib/colors";
import { money, num } from "@/lib/format";

type Exec = {
  kpis: Record<string, number>;
  growth: Record<string, number | null>;
  segments: { segment: string; customers: number; avg_savings: number; avg_card_spend: number }[];
  age: { age: number; segment: string }[];
  tier: { tier: string; segment: string; customers: number }[];
  portfolio: { pool: string; amount: number }[];
};

export default function ExecutivePage() {
  const { data, error, isLoading } = useApi<Exec>("executive");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const k = data.kpis;
  const gr = data.growth;
  const top = [...data.segments].sort((a, b) => b.customers - a.customers)[0];
  const total = num(k.customers);
  const relationship = num(k.total_savings) + num(k.total_deposit);
  const sav = num(data.portfolio.find((p) => p.pool === "Savings")?.amount);
  const loan = num(data.portfolio.find((p) => p.pool === "Loans")?.amount);

  return (
    <div className="space-y-5">
      <PageHeader title="Executive overview" />
      <KpiRow>
        <KpiCard label="Customers" value={total.toLocaleString()} delta={gr.customers} />
        <KpiCard label="Total savings" value={money(k.total_savings)} delta={gr.total_savings} />
        <KpiCard label="Total loans" value={money(k.total_loans)} delta={gr.total_loans} />
        <KpiCard label="Avg propensity" value={`${num(k.avg_ips).toFixed(0)}/100`} delta={gr.avg_ips} />
      </KpiRow>
      <KpiRow>
        <KpiCard label="Avg age" value={num(k.avg_age).toFixed(0)} />
        <KpiCard label="Mortgage holders" value={`${(num(k.pct_mortgage) * 100).toFixed(0)}%`} delta={gr.pct_mortgage} />
        <KpiCard label="30-day card spend" value={money(k.total_card_spend)} delta={gr.total_card_spend} />
        <KpiCard label="Loan-to-savings" value={num(k.ltv).toFixed(2)} delta={gr.ltv} />
      </KpiRow>

      <Insight>
        <b>{top.customers} of {total}</b> customers are <b>{top.segment}</b>. Total relationship balances
        (savings + deposits) are <b>{money(relationship)}</b>, with <b>{(num(k.pct_mortgage) * 100).toFixed(0)}%</b> holding a mortgage.
      </Insight>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Customers by propensity segment"
          caption={<><b>{top.segment}</b> is {((top.customers / total) * 100).toFixed(0)}% of the base — growth means migrating mass-retail clients upward.</>}>
          <VBars data={data.segments} xKey="segment" valueKey="customers" colorKey="segment" colorMap={SEGMENT_COLORS} />
        </ChartCard>
        <ChartCard title="Age distribution"
          caption={<>Average age <b>{num(k.avg_age).toFixed(0)}</b> — prime windows for life-stage offers (home, education, retirement).</>}>
          <Histogram data={data.age} valueKey="age" refLine={num(k.avg_age)} />
        </ChartCard>
        <ChartCard title="Tier × propensity segment"
          caption={<>HNW / AFFLUENT tiers concentrate the investor & digital-shopper segments — focus wealth offers there.</>}>
          <GroupedBars data={data.tier} xKey="tier" seriesKey="segment" valueKey="customers" colorMap={SEGMENT_COLORS} />
        </ChartCard>
        <ChartCard title="Portfolio composition"
          caption={<>Savings <b>{money(sav)}</b> vs loans <b>{money(loan)}</b> — a deposit-rich <b>{(sav / (loan || 1)).toFixed(1)}:1</b> book.</>}>
          <HBars data={data.portfolio} yKey="pool" valueKey="amount" />
        </ChartCard>
      </div>
    </div>
  );
}
