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
  const totalCust = data.rfm.reduce((a, r) => a + num(r.customers), 0) || 1;
  const atRiskPct = (num(k.at_risk) / totalCust) * 100;
  const stretched = data.health.find((h) => h.band === "Stretched")?.customers ?? 0;
  const stretchedPct = (num(stretched) / totalCust) * 100;
  const nbpTotal = data.nbp.reduce((a, n) => a + num(n.customers), 0) || 1;
  const topNbpPct = topNbp ? (num(topNbp.customers) / nbpTotal) * 100 : 0;
  const lowSow = data.sow.filter((s) => s.band === "0-10%" || s.band === "10-25%").reduce((a, s) => a + num(s.customers), 0);
  const lowSowPct = (lowSow / totalCust) * 100;

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
          caption={<><b>{num(k.at_risk).toLocaleString()}</b> customers (<b>{atRiskPct.toFixed(0)}%</b>) are At-risk/Hibernating — a defined win-back list; <b>{champions?.customers ?? 0}</b> Champions are ripe for advocacy & upsell.</>}>
          <VBars data={rfm} xKey="rfm_segment" valueKey="customers" />
        </ChartCard>
        <ChartCard title="Financial-health bands"
          caption={<><b>{num(stretched).toLocaleString()}</b> customers (<b>{stretchedPct.toFixed(0)}%</b>) are financially stretched — proactive budgeting tools & responsible-lending reduce future default and protect the brand.</>}>
          <Donut data={data.health} nameKey="band" valueKey="customers" colorMap={HEALTH_COLORS} />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Next-Best-Product targets"
          caption={<><b>{topNbp?.product}</b> is the top recommendation for <b>{num(topNbp?.customers).toLocaleString()}</b> customers (<b>{topNbpPct.toFixed(0)}%</b>) — a ready-made priority campaign with model-ranked targeting.</>}>
          <HBars data={[...data.nbp].sort((a, b) => num(a.customers) - num(b.customers))} yKey="product" valueKey="customers" />
        </ChartCard>
        <ChartCard title="Share-of-wallet distribution"
          caption={<><b>{lowSow.toLocaleString()}</b> customers (<b>{lowSowPct.toFixed(0)}%</b>) sit below 25% share-of-wallet — the clearest cross-sell whitespace to capture more of their financial life.</>}>
          <VBars data={data.sow} xKey="band" valueKey="customers" />
        </ChartCard>
      </div>
    </div>
  );
}
