"use client";

import Link from "next/link";
import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, VBars, Histogram } from "@/components/charts";
import { DataTable } from "@/components/data-table";
import { money, num } from "@/lib/format";

type Fin = {
  buckets: { bucket: string; customers: number; arrears: number }[];
  dpd: { dpd: number }[];
  kpis: { financed: number; npf: number; npf_rate: number; avg_on_time: number; total_arrears: number };
  worst: { customer_id: string; full_name: string; customer_segment: string; current_dpd: number; arrears_bucket: string; total_arrears: number }[];
};

export default function FinancingHealthPage() {
  const { data, error, isLoading } = useApi<Fin>("financing-health");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const k = data.kpis;
  const delinquent = data.buckets.filter((b) => b.bucket !== "Current").reduce((s, b) => s + num(b.customers), 0);
  const early = data.buckets.filter((b) => b.bucket === "1-30" || b.bucket === "31-60").reduce((s, b) => s + num(b.customers), 0);
  const npfArrears = num(data.buckets.find((b) => b.bucket === "90+")?.arrears ?? 0);
  const lateArrears = num(data.buckets.filter((b) => b.bucket !== "Current").reduce((s, b) => s + num(b.arrears), 0));

  return (
    <div className="space-y-5">
      <PageHeader title="Financing health & arrears" subtitle="Repayment performance, days-past-due and non-performing financing across the book." />
      <KpiRow>
        <KpiCard label="Financed customers" value={num(k.financed).toLocaleString()} />
        <KpiCard label="On-time rate" value={`${(num(k.avg_on_time) * 100).toFixed(0)}%`} />
        <KpiCard label="NPF rate" value={`${(num(k.npf_rate) * 100).toFixed(1)}%`} accent="danger" />
        <KpiCard label="Total arrears" value={money(k.total_arrears)} accent="danger" />
      </KpiRow>

      <Insight>
        <b>{delinquent}</b> of <b>{num(k.financed).toLocaleString()}</b> financed customers are in arrears;
        <b> {num(k.npf)}</b> are non-performing (DPD&gt;90, {(num(k.npf_rate) * 100).toFixed(1)}%). Early buckets
        (1–30, 31–60) are the priority for collections outreach before they roll into NPF.
      </Insight>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Customers by arrears bucket"
          caption={<><b>{early.toLocaleString()}</b> customers sit in the early 1–30/31–60 buckets — intervening now prevents roll-forward into the <b>{money(npfArrears)}</b> NPF bucket; early collections is the cheapest credit-loss lever.</>}>
          <VBars data={data.buckets} xKey="bucket" valueKey="customers" />
        </ChartCard>
        <ChartCard title="Days-past-due distribution (delinquent)"
          caption={<><b>{money(lateArrears)}</b> in total arrears is exposed across delinquent accounts; the right-tail (DPD&gt;90) is the provisioning/write-off risk to ring-fence.</>}>
          <Histogram data={data.dpd} valueKey="dpd" bins={12} color="#C62828" />
        </ChartCard>
      </div>

      <DataTable title="Collections priority — highest DPD" rows={data.worst}
        columns={[
          { key: "customer_id", label: "CIF", fmt: (v) => <Link href={`/customers/${v}`} className="text-primary hover:underline">{String(v)}</Link> },
          { key: "full_name", label: "Name" },
          { key: "customer_segment", label: "Tier" },
          { key: "current_dpd", label: "DPD", align: "right" },
          { key: "arrears_bucket", label: "Bucket" },
          { key: "total_arrears", label: "Arrears", align: "right", fmt: (v) => money(v as number) },
        ]} />
    </div>
  );
}
