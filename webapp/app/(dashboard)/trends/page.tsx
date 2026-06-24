"use client";

import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, MultiLine, StackArea, VBars } from "@/components/charts";
import { CHANNEL_COLORS } from "@/lib/colors";
import { money, num } from "@/lib/format";

type Trends = {
  daily: { txn_date: string; channel: string; spend: number }[];
  weekly: { week: string; category: string; spend: number }[];
  atm: { week: string; withdrawals: number; amount: number }[];
};

export default function TrendsPage() {
  const { data, error, isLoading } = useApi<Trends>("trends");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const totalSpend = data.daily.reduce((s, d) => s + num(d.spend), 0);
  const credit = data.daily.filter((d) => d.channel === "Credit").reduce((s, d) => s + num(d.spend), 0);
  const catTotals = new Map<string, number>();
  for (const w of data.weekly) catTotals.set(w.category, (catTotals.get(w.category) ?? 0) + num(w.spend));
  const topCat = [...catTotals.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—";
  const peakAtm = Math.max(...data.atm.map((a) => num(a.withdrawals)), 0);

  return (
    <div className="space-y-5">
      <PageHeader title="Spend & transaction trends" subtitle="Card-transaction facts over the trailing 90 days (credit + debit purchases)." />
      <KpiRow>
        <KpiCard label="90-day spend" value={money(totalSpend)} />
        <KpiCard label="Credit share" value={`${((credit / (totalSpend || 1)) * 100).toFixed(0)}%`} />
        <KpiCard label="Top category" value={topCat} />
        <KpiCard label="Peak ATM / week" value={String(peakAtm)} />
      </KpiRow>

      <Insight>
        Customers spent <b>{money(totalSpend)}</b> on cards in 90 days — <b>{((credit / (totalSpend || 1)) * 100).toFixed(0)}%</b> credit
        / <b>{(((totalSpend - credit) / (totalSpend || 1)) * 100).toFixed(0)}%</b> debit. <b>{topCat}</b> is the largest category by value.
      </Insight>

      <ChartCard title="Daily spend — credit vs debit"
        caption={<>Credit consistently outpaces debit — the primary rail to build rewards/limit strategies around.</>}>
        <MultiLine data={data.daily} indexKey="txn_date" seriesKey="channel" valueKey="spend" colorMap={CHANNEL_COLORS} height={320} />
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Weekly category mix"
          caption={<><b>{topCat}</b> leads weekly card value; the mix is stable week-to-week.</>}>
          <StackArea data={data.weekly} indexKey="week" seriesKey="category" valueKey="spend" />
        </ChartCard>
        <ChartCard title="ATM withdrawals per week"
          caption={<>ATM use peaks at <b>{peakAtm}</b> withdrawals in a week — rising cash-out is an early churn cue.</>}>
          <VBars data={data.atm} xKey="week" valueKey="withdrawals" color="#C62828" />
        </ChartCard>
      </div>
    </div>
  );
}
