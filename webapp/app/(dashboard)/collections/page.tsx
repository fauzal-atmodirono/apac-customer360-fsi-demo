"use client";

import Link from "next/link";
import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, VBars, GroupedBars, Donut, StackArea } from "@/components/charts";
import { DataTable } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { money, num } from "@/lib/format";

type Collections = {
  kpis: { active_cases: number; total_cases: number; under_collection: number; recovered: number; recovery_rate: number; restructured_amount: number };
  byStage: { stage: string; cases: number; outstanding: number; recovered: number }[];
  statusMix: { status: string; cases: number }[];
  trend: { month: string; type: string; amount: number }[];
  channel: { channel: string; actions: number; contact_rate: number; ptp_kept_rate: number }[];
  worklist: { case_id: string; customer_id: string; full_name: string; stage: string; case_status: string; collector: string; current_dpd: number; collectibility_label: string | null; outstanding: number; recovered: number; ptp_made: number; ptp_kept: number }[];
  collectibility: { collectibility: number; kol: string; customers: number; arrears: number }[];
};

const kolVariant = (label: string) =>
  label.startsWith("Kol-1") ? "success" :
  label.startsWith("Kol-2") ? "warning" : "danger";

const statusVariant = (s: string) =>
  s === "LEGAL" || s === "WRITTEN_OFF" ? "danger" :
  s === "RECOVERED" || s === "RESTRUCTURED" ? "success" :
  s === "PARTIAL_RECOVERY" || s === "PTP_OBTAINED" ? "warning" : "muted";

export default function CollectionsPage() {
  const { data, error, isLoading } = useApi<Collections>("collections");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const k = data.kpis;
  const stageFlow = data.byStage.flatMap((s) => [
    { stage: s.stage, series: "Outstanding", value: num(s.outstanding) },
    { stage: s.stage, series: "Recovered", value: num(s.recovered) },
  ]);
  const bestChannel = [...data.channel].filter((c) => num(c.ptp_kept_rate) > 0)
    .sort((a, b) => num(b.ptp_kept_rate) - num(a.ptp_kept_rate))[0];
  const earlyStage = data.byStage.filter((s) => s.stage === "SOFT_REMINDER" || s.stage === "INTENSIVE");
  const earlyOutstanding = earlyStage.reduce((a, s) => a + num(s.outstanding) - num(s.recovered), 0);
  const resolved = data.statusMix.filter((s) => ["RECOVERED", "RESTRUCTURED"].includes(s.status))
    .reduce((a, s) => a + num(s.cases), 0);

  return (
    <div className="space-y-5">
      <PageHeader title="Collections & recovery" subtitle="Delinquent-financing caseload, outreach effectiveness, promises-to-pay and cash recovered — aligned with Financing health." />
      <KpiRow>
        <KpiCard label="Active cases" value={num(k.active_cases).toLocaleString()} sub={`of ${num(k.total_cases)} total`} accent="danger" />
        <KpiCard label="Under collection" value={money(k.under_collection)} accent="danger" />
        <KpiCard label="Cash recovered" value={money(k.recovered)} accent="success" />
        <KpiCard label="Recovery rate" value={`${(num(k.recovery_rate) * 100).toFixed(0)}%`} sub={`+ ${money(k.restructured_amount)} restructured (R&R)`} />
      </KpiRow>

      <Insight tone="warning">
        <b>{num(k.active_cases)}</b> cases remain active with <b>{money(k.under_collection)}</b> still under collection;
        <b> {money(k.recovered)}</b> ({(num(k.recovery_rate) * 100).toFixed(0)}%) has been recovered in cash and
        <b> {money(k.restructured_amount)}</b> resolved via R&amp;R restructuring. <b>{resolved}</b> cases are fully
        resolved — early-bucket intervention is keeping roll-forward into NPF contained.
      </Insight>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Outstanding vs recovered by stage"
          caption={<><b>{money(earlyOutstanding)}</b> of unrecovered arrears sits in the early SOFT/INTENSIVE stages — the cheapest to collect; every ringgit recovered here avoids field visits and legal cost downstream.</>}>
          <GroupedBars data={stageFlow} xKey="stage" seriesKey="series" valueKey="value"
            colorMap={{ Outstanding: "#C62828", Recovered: "#2E7D32" }} />
        </ChartCard>
        <ChartCard title="Case status mix"
          caption={<><b>{resolved}</b> of {num(k.total_cases)} cases are fully resolved (recovered or restructured) — the remainder is the live worklist; LEGAL/WRITTEN_OFF cases are the credit-loss tail to minimise.</>}>
          <Donut data={data.statusMix} nameKey="status" valueKey="cases" />
        </ChartCard>
      </div>

      <ChartCard title="Collectibility distribution (Kol-1 Current → Kol-5 Loss)"
        caption={<>Regulatory 5-class collectibility derived from days-past-due (demo OJK-style bands). Kol-3 and worse is the NPF tail — <b>{data.collectibility.filter((c) => c.collectibility >= 3).reduce((a, c) => a + num(c.customers), 0)}</b> customers whose arrears need intensive recovery.</>}>
        <VBars data={data.collectibility} xKey="kol" valueKey="customers" />
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Recovery flow (monthly, by type)"
          caption={<>Cash payments dominate recoveries, with <b>R&amp;R restructuring</b> and capped <b>ta'widh</b> compensation (Shariah-compliant, non-compounding) supplementing — no penalty interest anywhere in the flow.</>}>
          <StackArea data={data.trend} indexKey="month" seriesKey="type" valueKey="amount" />
        </ChartCard>
        <ChartCard title="Channel effectiveness (promise-kept rate)"
          caption={bestChannel
            ? <><b>{bestChannel.channel}</b> yields the highest kept-promise rate (<b>{(num(bestChannel.ptp_kept_rate) * 100).toFixed(0)}%</b>) — route early-stage outreach to the channels that convert promises into cash.</>
            : <>Promise-kept rate by outreach channel.</>}>
          <VBars data={data.channel.map((c) => ({ ...c, kept_pct: num(c.ptp_kept_rate) * 100 }))} xKey="channel" valueKey="kept_pct" />
        </ChartCard>
      </div>

      <DataTable title="Collections worklist — largest open balances" rows={data.worklist}
        columns={[
          { key: "customer_id", label: "CIF", fmt: (v) => <Link href={`/customers/${v}`} className="text-primary hover:underline">{String(v)}</Link> },
          { key: "full_name", label: "Name" },
          { key: "stage", label: "Stage", fmt: (v) => <Badge variant="muted">{String(v)}</Badge> },
          { key: "case_status", label: "Status", fmt: (v) => <Badge variant={statusVariant(String(v))}>{String(v)}</Badge> },
          { key: "collector", label: "Collector" },
          { key: "collectibility_label", label: "Kol", fmt: (v) => v ? <Badge variant={kolVariant(String(v))}>{String(v)}</Badge> : "—" },
          { key: "current_dpd", label: "DPD", align: "right" },
          { key: "outstanding", label: "Outstanding", align: "right", fmt: (v) => money(v as number) },
          { key: "recovered", label: "Recovered", align: "right", fmt: (v) => money(v as number) },
        ]} />
    </div>
  );
}
