"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight, Search } from "lucide-react";
import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader } from "@/components/insight";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SEGMENT_COLORS, CHURN_COLORS } from "@/lib/colors";
import { money, num } from "@/lib/format";

type Row = {
  customer_id: string; full_name: string; customer_segment: string; region: string;
  savings: number; ips: number; propensity_score_segment: string; churn_risk_segment: string;
};
const churnVariant = (b: string) => (b === "HIGH" ? "danger" : b === "MEDIUM" ? "warning" : "success");

export default function CustomersPage() {
  const { data, error, isLoading } = useApi<{ customers: Row[] }>("customers");
  const [qStr, setQStr] = useState("");
  const [seg, setSeg] = useState("ALL");

  const rows = useMemo(() => {
    const all = data?.customers ?? [];
    const term = qStr.trim().toLowerCase();
    return all.filter((r) =>
      (seg === "ALL" || r.propensity_score_segment === seg) &&
      (!term || r.full_name.toLowerCase().includes(term) || r.customer_id.includes(term)),
    ).slice(0, 200);
  }, [data, qStr, seg]);

  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const segments = ["ALL", ...Array.from(new Set(data.customers.map((c) => c.propensity_score_segment)))];

  return (
    <div className="space-y-5">
      <PageHeader title="Customers" subtitle={`${data.customers.length.toLocaleString()} customers · click a row for the full 360 profile`} />

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            value={qStr} onChange={(e) => setQStr(e.target.value)}
            placeholder="Search by name or CIF…"
            className="w-full rounded-lg border bg-card py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <select value={seg} onChange={(e) => setSeg(e.target.value)}
          className="rounded-lg border bg-card px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring">
          {segments.map((s) => <option key={s} value={s}>{s === "ALL" ? "All segments" : s}</option>)}
        </select>
      </div>

      <Card className="overflow-hidden p-0">
        <table className="w-full text-sm">
          <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-4 py-2.5 text-left">CIF</th>
              <th className="px-4 py-2.5 text-left">Name</th>
              <th className="px-4 py-2.5 text-left">Segment</th>
              <th className="px-4 py-2.5 text-left">Region</th>
              <th className="px-4 py-2.5 text-right">Savings</th>
              <th className="px-4 py-2.5 text-right">IPS</th>
              <th className="px-4 py-2.5 text-left">Churn</th>
              <th className="px-4 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.customer_id} className="border-t hover:bg-accent/40">
                <td className="px-4 py-2 font-mono text-xs">
                  <Link href={`/customers/${r.customer_id}`} className="hover:underline">{r.customer_id}</Link>
                </td>
                <td className="px-4 py-2">
                  <Link href={`/customers/${r.customer_id}`} className="font-medium hover:underline">{r.full_name}</Link>
                </td>
                <td className="px-4 py-2">
                  <span className="inline-flex items-center gap-1.5 text-xs">
                    <span className="h-2 w-2 rounded-full" style={{ background: SEGMENT_COLORS[r.propensity_score_segment] ?? "#94A3B8" }} />
                    {r.propensity_score_segment}
                  </span>
                </td>
                <td className="px-4 py-2 text-muted-foreground">{r.region}</td>
                <td className="px-4 py-2 text-right tabular-nums">{money(r.savings)}</td>
                <td className="px-4 py-2 text-right tabular-nums">{num(r.ips).toFixed(0)}</td>
                <td className="px-4 py-2"><Badge variant={churnVariant(r.churn_risk_segment)}>{r.churn_risk_segment}</Badge></td>
                <td className="px-4 py-2 text-right">
                  <Link href={`/customers/${r.customer_id}`}><ChevronRight className="h-4 w-4 text-muted-foreground" /></Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p className="p-6 text-center text-sm text-muted-foreground">No customers match.</p>}
      </Card>
      {rows.length === 200 && <p className="text-xs text-muted-foreground">Showing first 200 — refine your search.</p>}
    </div>
  );
}
