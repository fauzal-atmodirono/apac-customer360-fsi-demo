"use client";

import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, VBars } from "@/components/charts";
import { DataTable } from "@/components/data-table";
import { num } from "@/lib/format";

type Campaigns = {
  campaigns: { campaign_name: string; product_name: string; channel: string; sent: number; opened: number; clicked: number; converted: number; conversion_rate: number; roi: number }[];
  byChannel: { channel: string; sent: number; converted: number; conversion_rate: number }[];
  kpis: { sent: number; opened: number; clicked: number; converted: number; conversion_rate: number; avg_roi: number };
};

export default function CampaignsPage() {
  const { data, error, isLoading } = useApi<Campaigns>("campaigns");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const k = data.kpis;
  const funnel = [
    { stage: "Sent", count: num(k.sent) },
    { stage: "Opened", count: num(k.opened) },
    { stage: "Clicked", count: num(k.clicked) },
    { stage: "Converted", count: num(k.converted) },
  ];
  const best = [...data.campaigns].sort((a, b) => num(b.conversion_rate) - num(a.conversion_rate))[0];
  const click2conv = num(k.clicked) ? (num(k.converted) / num(k.clicked)) * 100 : 0;
  const open2click = num(k.opened) ? (num(k.clicked) / num(k.opened)) * 100 : 0;
  const bestChannel = [...data.byChannel].sort((a, b) => num(b.conversion_rate) - num(a.conversion_rate))[0];

  return (
    <div className="space-y-5">
      <PageHeader title="Campaign performance" subtitle="Outreach funnel, conversion and ROI across product campaigns and channels." />
      <KpiRow>
        <KpiCard label="Messages sent" value={num(k.sent).toLocaleString()} />
        <KpiCard label="Conversions" value={num(k.converted).toLocaleString()} />
        <KpiCard label="Conversion rate" value={`${(num(k.conversion_rate) * 100).toFixed(1)}%`} />
        <KpiCard label="Avg ROI" value={`${num(k.avg_roi).toFixed(1)}×`} />
      </KpiRow>

      <Insight>
        Across <b>{data.campaigns.length}</b> campaigns, <b>{num(k.converted).toLocaleString()}</b> of
        <b> {num(k.sent).toLocaleString()}</b> targeted customers converted ({(num(k.conversion_rate) * 100).toFixed(1)}%).
        <b> {best?.campaign_name}</b> leads on conversion — replicate its targeting and channel.
      </Insight>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Overall funnel"
          caption={<>Only <b>{click2conv.toFixed(0)}%</b> of clicks convert (vs <b>{open2click.toFixed(0)}%</b> open→click) — the click→convert step is the biggest leak; sharper offer relevance & follow-up here lifts conversions fastest.</>}>
          <VBars data={funnel} xKey="stage" valueKey="count" />
        </ChartCard>
        <ChartCard title="Conversion rate by channel"
          caption={<><b>{bestChannel?.channel}</b> converts best at <b>{(num(bestChannel?.conversion_rate) * 100).toFixed(1)}%</b> — shift budget toward the highest-ROI channels and reserve costly branch outreach for high-value targets.</>}>
          <VBars data={data.byChannel} xKey="channel" valueKey="conversion_rate" />
        </ChartCard>
      </div>

      <DataTable title="Campaigns" rows={data.campaigns}
        columns={[
          { key: "campaign_name", label: "Campaign" },
          { key: "product_name", label: "Product" },
          { key: "channel", label: "Channel" },
          { key: "sent", label: "Sent", align: "right", fmt: (v) => num(v).toLocaleString() },
          { key: "converted", label: "Converted", align: "right", fmt: (v) => num(v).toLocaleString() },
          { key: "conversion_rate", label: "Conv. rate", align: "right", fmt: (v) => `${(num(v) * 100).toFixed(1)}%` },
          { key: "roi", label: "ROI", align: "right", fmt: (v) => `${num(v).toFixed(1)}×` },
        ]} />
    </div>
  );
}
