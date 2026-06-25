"use client";

import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, VBars, StackArea } from "@/components/charts";
import { money, num } from "@/lib/format";

type Social = {
  byType: { type: string; contributors: number; total: number }[];
  monthly: { month: string; type: string; total: number }[];
  hajj: { customers: number };
  itekad: { customers: number; total: number };
  kpis: { zakat_payers: number; zakat_total: number };
};

export default function SocialFinancePage() {
  const { data, error, isLoading } = useApi<Social>("social-finance");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const zakat = data.byType.find((t) => t.type === "ZAKAT");
  const totalGiving = data.byType.reduce((s, t) => s + num(t.total), 0);
  const zakatShare = totalGiving ? (num(zakat?.total) / totalGiving) * 100 : 0;
  const peak = [...data.monthly].sort((a, b) => num(b.total) - num(a.total))[0];

  return (
    <div className="space-y-5">
      <PageHeader title="Islamic social finance" subtitle="Zakat, Sadaqah & Wakaf contributions, Hajj savings, and iTEKAD microfinance — Bank Muamalat's social mandate." />
      <KpiRow>
        <KpiCard label="Total social giving" value={money(totalGiving)} />
        <KpiCard label="Zakat contributors" value={num(zakat?.contributors).toLocaleString()} sub={money(zakat?.total)} />
        <KpiCard label="Tabung Haji savers" value={num(data.hajj?.customers).toLocaleString()} />
        <KpiCard label="iTEKAD recipients" value={num(data.itekad?.customers).toLocaleString()} sub={money(data.itekad?.total)} />
      </KpiRow>

      <Insight>
        Customers contributed <b>{money(totalGiving)}</b> through Zakat, Sadaqah and Wakaf;
        <b> {num(zakat?.contributors).toLocaleString()}</b> paid Zakat (<b>{money(zakat?.total)}</b>).
        <b> {num(data.itekad?.customers).toLocaleString()}</b> B40 entrepreneurs are supported via iTEKAD microfinance —
        differentiators rooted in Bank Muamalat's Islamic social mandate.
      </Insight>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Contributions by type"
          caption={<>Zakat is <b>{zakatShare.toFixed(0)}%</b> of social giving (<b>{money(zakat?.total)}</b>) — a recurring, faith-driven flow the bank can grow via Ez-Zakat & auto-calculation, deepening loyalty and ESG standing.</>}>
          <VBars data={data.byType} xKey="type" valueKey="total" />
        </ChartCard>
        <ChartCard title="Social giving over time"
          caption={<>Giving peaks in <b>{peak?.month ?? "Ramadan season"}</b> — plan Zakat/Sadaqah/Wakaf campaigns and liquidity around religious seasons to capture the surge.</>}>
          <StackArea data={data.monthly} indexKey="month" seriesKey="type" valueKey="total" />
        </ChartCard>
      </div>
    </div>
  );
}
