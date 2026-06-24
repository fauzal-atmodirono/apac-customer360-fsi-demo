"use client";

import { Lock, Unlock } from "lucide-react";
import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { DataTable } from "@/components/data-table";
import { Card } from "@/components/ui/card";

type Row = { customer_id: string; full_name: string; phone_number: string; address: string | null; card_number: string };
type Gov = { cleartext: Row[]; masked: Row[] };

const COLS = [
  { key: "customer_id", label: "CIF" },
  { key: "full_name", label: "Full name" },
  { key: "phone_number", label: "Phone" },
  { key: "address", label: "Address", fmt: (v: unknown) => (v == null ? <span className="text-muted-foreground">NULL</span> : String(v)) },
  { key: "card_number", label: "Card PAN" },
];

export default function GovernancePage() {
  const { data, error, isLoading } = useApi<Gov>("governance");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  return (
    <div className="space-y-5">
      <PageHeader title="Governance: column-level security"
        subtitle="Same rows, two identities. PII columns carry BigQuery policy tags with dynamic data masking — enforced by the engine, not the app." />
      <Insight tone="success">
        <b>4 columns</b> are policy-tag protected: name, phone, address, and card PAN. Access resolves per-identity at query time.
      </Insight>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium text-success"><Unlock className="h-4 w-4" /> Fine-grained reader (you)</div>
          <DataTable title="" columns={COLS} rows={data.cleartext} />
          <p className="text-xs text-muted-foreground">💡 Authorized roles (e.g. marketing) see full PII to action campaigns.</p>
        </div>
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium text-danger"><Lock className="h-4 w-4" /> Masked reader (service account)</div>
          <DataTable title="" columns={COLS} rows={data.masked} />
          <p className="text-xs text-muted-foreground">💡 The same query returns SHA-256 names, redacted phones/cards and NULL addresses for everyone else.</p>
        </div>
      </div>

      <Card className="p-5">
        <h3 className="mb-3 text-sm font-semibold">Masking policy</h3>
        <table className="w-full text-sm">
          <thead className="text-xs uppercase text-muted-foreground"><tr><th className="py-1 text-left">Policy tag</th><th className="text-left">Column</th><th className="text-left">Rule</th></tr></thead>
          <tbody className="[&_td]:py-1.5 [&_tr]:border-t">
            <tr><td><code>PII_Name</code></td><td>full_name</td><td>SHA-256 hash</td></tr>
            <tr><td><code>PII_Phone</code></td><td>phone_number</td><td>custom routine → XXXX-XXXX-####</td></tr>
            <tr><td><code>PII_Address</code></td><td>address</td><td>nullify → NULL</td></tr>
            <tr><td><code>Card_PAN</code></td><td>card_number</td><td>custom routine → XXXXXXXXXXXX####</td></tr>
          </tbody>
        </table>
      </Card>
    </div>
  );
}
