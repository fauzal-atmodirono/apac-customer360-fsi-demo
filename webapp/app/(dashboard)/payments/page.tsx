"use client";

import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, VBars, HBars, Donut } from "@/components/charts";
import { money, num } from "@/lib/format";

type Pay = {
  byType: { type: string; txns: number; value: number; fees: number }[];
  corridors: { corridor: string; txns: number; value: number }[];
  channels: { channel: string; txns: number; amount: number }[];
  cash: { type: string; amount: number }[];
  kpis: { transfers: number; fee_income: number; remitters: number; avg_digital: number };
};

export default function PaymentsPage() {
  const { data, error, isLoading } = useApi<Pay>("payments");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const k = data.kpis;
  const topType = [...data.byType].sort((a, b) => num(b.value) - num(a.value))[0];
  const topCorridor = data.corridors[0];
  const intlFees = num([...data.byType].find((t) => t.type === "INTL")?.fees ?? 0);
  const branch = data.channels.find((c) => c.channel === "BRANCH");
  const channelTotal = data.channels.reduce((a, c) => a + num(c.txns), 0) || 1;
  const branchPct = branch ? (num(branch.txns) / channelTotal) * 100 : 0;
  const corridorTop3 = [...data.corridors].slice(0, 3).reduce((a, c) => a + num(c.value), 0);

  return (
    <div className="space-y-5">
      <PageHeader title="Payments & channels" subtitle="Fund transfers, remittance corridors, fee income, and cash channel usage." />
      <KpiRow>
        <KpiCard label="Transfers" value={num(k.transfers).toLocaleString()} />
        <KpiCard label="Transfer fee income" value={money(k.fee_income)} />
        <KpiCard label="Remitters (intl)" value={num(k.remitters).toLocaleString()} />
        <KpiCard label="Self-service ratio" value={`${(num(k.avg_digital) * 100).toFixed(0)}%`} />
      </KpiRow>

      <Insight>
        <b>{topType?.type}</b> dominates transfer value; fee income totals <b>{money(k.fee_income)}</b>.
        <b> {num(k.remitters).toLocaleString()}</b> customers send international remittances{topCorridor ? <> — <b>{topCorridor.corridor}</b> is the top corridor</> : null}.
        Cash is <b>{(num(k.avg_digital) * 100).toFixed(0)}%</b> self-service (ATM/CDM) — branch migration headroom.
      </Insight>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Transfer value by type"
          caption={<><b>{topType?.type}</b> carries the most value; international transfers — though fewer — generate <b>{money(intlFees)}</b> of fee income, the highest-margin transfer rail to grow.</>}>
          <VBars data={data.byType} xKey="type" valueKey="value" />
        </ChartCard>
        <ChartCard title="Remittance corridors (intl value)"
          caption={<><b>{topCorridor?.corridor}</b> leads outbound remittance; the top 3 corridors move <b>{money(corridorTop3)}</b> — target FX, remittance bundles & diaspora products at these communities.</>}>
          <HBars data={[...data.corridors].sort((a, b) => num(a.value) - num(b.value))} yKey="corridor" valueKey="value" />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Cash transactions by channel"
          caption={<><b>{branchPct.toFixed(0)}%</b> of cash transactions still go through the <b>branch</b> — migrating routine cash to ATM/CDM cuts cost-to-serve and frees staff for advisory & sales.</>}>
          <Donut data={data.channels} nameKey="channel" valueKey="txns" />
        </ChartCard>
        <ChartCard title="Cash in vs out"
          caption={<>Net cash flow across the network sizes vault/ATM cash-management needs; persistent net-withdrawal points to cash-reliant segments to nudge toward digital payments.</>}>
          <VBars data={data.cash} xKey="type" valueKey="amount" />
        </ChartCard>
      </div>
    </div>
  );
}
