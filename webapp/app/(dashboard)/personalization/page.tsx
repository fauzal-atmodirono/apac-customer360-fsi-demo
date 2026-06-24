"use client";

import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, VBars, HBars, Donut } from "@/components/charts";
import { num } from "@/lib/format";

type Pers = {
  rfm: { rfm_segment: string; customers: number }[];
  health: { band: string; customers: number }[];
  nbp: { product: string; customers: number }[];
  sow: { band: string; customers: number }[];
  kpis: { avg_health: number; avg_sow: number; at_risk: number; stretched: number };
};

const RFM_ORDER = ["Champions", "Loyal", "Potential", "New / Promising", "At risk", "Hibernating", "Needs attention"];
const HEALTH_COLORS = { Healthy: "#2E7D32", Moderate: "#F9A825", Stretched: "#C62828" };

export default function PersonalizationPage() {
  const { data, error, isLoading } = useApi<Pers>("personalization");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const k = data.kpis;
  const rfm = [...data.rfm].sort((a, b) => RFM_ORDER.indexOf(a.rfm_segment) - RFM_ORDER.indexOf(b.rfm_segment));
  const champions = data.rfm.find((r) => r.rfm_segment === "Champions");
  const topNbp = [...data.nbp].sort((a, b) => num(b.customers) - num(a.customers))[0];

  return (
    <div className="space-y-5">
      <PageHeader title="Hyper-personalization signals" subtitle="RFM behaviour, financial health, share-of-wallet, and Next-Best-Product propensity across the book." />
      <KpiRow>
        <KpiCard label="Avg financial health" value={`${num(k.avg_health).toFixed(0)}/100`} />
        <KpiCard label="Avg share-of-wallet" value={`${(num(k.avg_sow) * 100).toFixed(0)}%`} />
        <KpiCard label="At-risk / hibernating" value={num(k.at_risk).toLocaleString()} accent="danger" />
        <KpiCard label="Financially stretched" value={num(k.stretched).toLocaleString()} accent="danger" />
      </KpiRow>

      <Insight>
        <b>{champions?.customers ?? 0}</b> Champions anchor the book; <b>{num(k.at_risk).toLocaleString()}</b> customers
        are at-risk or hibernating (reactivation targets). The most common Next-Best-Product is <b>{topNbp?.product}</b>.
      </Insight>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="RFM behavioral segments"
          caption={<>Prioritise <b>At risk</b> &amp; <b>Hibernating</b> for win-back, and <b>Champions</b> for advocacy/upsell.</>}>
          <VBars data={rfm} xKey="rfm_segment" valueKey="customers" />
        </ChartCard>
        <ChartCard title="Financial-health bands"
          caption={<><b>{data.health.find((h) => h.band === "Stretched")?.customers ?? 0}</b> customers are stretched — target with budgeting tools &amp; responsible-lending offers.</>}>
          <Donut data={data.health} nameKey="band" valueKey="customers" colorMap={HEALTH_COLORS} />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Next-Best-Product targets"
          caption={<><b>{topNbp?.product}</b> leads as the top recommended product across the base.</>}>
          <HBars data={[...data.nbp].sort((a, b) => num(a.customers) - num(b.customers))} yKey="product" valueKey="customers" />
        </ChartCard>
        <ChartCard title="Share-of-wallet distribution"
          caption={<>Low bands = whitespace where we capture little of the customer&apos;s spend — primary cross-sell opportunity.</>}>
          <VBars data={data.sow} xKey="band" valueKey="customers" />
        </ChartCard>
      </div>
    </div>
  );
}
