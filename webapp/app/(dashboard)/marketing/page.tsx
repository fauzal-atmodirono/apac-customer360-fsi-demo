"use client";

import Link from "next/link";
import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { ChartCard, HBars, Histogram, GroupedBars, Bubble } from "@/components/charts";
import { DataTable } from "@/components/data-table";
import { SEGMENT_COLORS } from "@/lib/colors";
import { money, num } from "@/lib/format";

type Mktg = {
  categories: { category: string; customers: number }[];
  ipsDist: { ips: number; segment: string }[];
  catBySegment: { segment: string; category: string; customers: number }[];
  crossSell: { customer_id: string; savings: number; cc_spend: number; ips: number; has_active_mortgage: boolean }[];
  hnwTargets: Record<string, unknown>[];
  hnwNoMortgage: Record<string, unknown>[];
};

export default function MarketingPage() {
  const { data, error, isLoading } = useApi<Mktg>("marketing");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const topCats = data.categories.slice(0, 3).map((c) => c.category);
  const n70 = data.ipsDist.filter((d) => num(d.ips) >= 70).length;
  const cross = data.crossSell.map((d) => ({ ...d, mortgage: d.has_active_mortgage ? "Has mortgage" : "No mortgage" }));

  return (
    <div className="space-y-5">
      <PageHeader title="Marketing / Next-Best-Action" />
      <Insight tone="success">
        <b>{data.hnwNoMortgage.length}</b> affluent customers (savings &gt; $100K) hold <b>no mortgage</b> — a prime
        home-lending cross-sell. The most common spending category is <b>{topCats[0] ?? "—"}</b>.
      </Insight>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Top spending categories"
          caption={<><b>{topCats.join(", ")}</b> lead — anchor merchant/cashback offers to these.</>}>
          <HBars data={[...data.categories].sort((a, b) => a.customers - b.customers)} yKey="category" valueKey="customers" />
        </ChartCard>
        <ChartCard title="Investment-propensity distribution"
          caption={<><b>{n70}</b> customers score 70+ IPS — the priority list for term-deposit & wealth campaigns.</>}>
          <Histogram data={data.ipsDist} valueKey="ips" />
        </ChartCard>
        <ChartCard title="Category mix by segment"
          caption={<>Mass-retail spend spreads across all categories; niche segments concentrate in a few — target by segment × category.</>}>
          <GroupedBars data={data.catBySegment} xKey="category" seriesKey="segment" valueKey="customers" colorMap={SEGMENT_COLORS} stacked />
        </ChartCard>
        <ChartCard title="Cross-sell map (savings vs card spend)"
          caption={<>Green points (no mortgage) with high savings are home-lending leads; bubble size = IPS.</>}>
          <Bubble data={cross} xKey="savings" yKey="cc_spend" sizeKey="ips" colorKey="mortgage"
            colorMap={{ "Has mortgage": "#94A3B8", "No mortgage": "#2E7D32" }} xLabel="savings" yLabel="CC spend 30d" />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <DataTable title="HNW investor targets" rows={data.hnwTargets}
          columns={[
            { key: "customer_id", label: "CIF", fmt: (v) => <Link href={`/customers/${v}`} className="text-primary hover:underline">{String(v)}</Link> }, { key: "full_name", label: "Name" },
            { key: "savings", label: "Savings", align: "right", fmt: (v) => money(v as number) },
            { key: "ips", label: "IPS", align: "right", fmt: (v) => num(v as number).toFixed(0) },
          ]} />
        <DataTable title="Mortgage cross-sell (HNW, no mortgage)" rows={data.hnwNoMortgage}
          columns={[
            { key: "customer_id", label: "CIF", fmt: (v) => <Link href={`/customers/${v}`} className="text-primary hover:underline">{String(v)}</Link> }, { key: "full_name", label: "Name" },
            { key: "savings", label: "Savings", align: "right", fmt: (v) => money(v as number) },
            { key: "top_spending_category", label: "Top cat" },
          ]} />
      </div>
    </div>
  );
}
