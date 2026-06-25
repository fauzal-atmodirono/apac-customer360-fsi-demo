"use client";

import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, VBars } from "@/components/charts";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { num } from "@/lib/format";

type Product = {
  product_code: string; product_name: string; category: string; islamic_contract: string;
  product_type: string; indicative_rate: number; holders: number;
};
type Products = {
  catalog: Product[];
  byCategory: { category: string; holders: number; holdings: number }[];
  perCustomer: { products: number; customers: number }[];
  kpis: { catalog_size: number; products_held: number; avg_products: number };
};

const TOTAL = 1003; // customer base for penetration %

export default function ProductsPage() {
  const { data, error, isLoading } = useApi<Products>("products");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const k = data.kpis;
  const cats = Array.from(new Set(data.catalog.map((p) => p.category)));
  const topCat = [...data.byCategory].sort((a, b) => num(b.holders) - num(a.holders))[0];
  const whitespace = [...data.catalog].filter((p) => p.product_type !== "SERVICE")
    .sort((a, b) => num(a.holders) - num(b.holders)).slice(0, 6);
  const shallow = data.perCustomer.filter((p) => num(p.products) <= 2).reduce((a, p) => a + num(p.customers), 0);

  return (
    <div className="space-y-5">
      <PageHeader title="Product catalog" subtitle="Bank Muamalat Malaysia Shariah-compliant consumer products — penetration & cross-sell whitespace." />
      <KpiRow>
        <KpiCard label="Catalog products" value={String(num(k.catalog_size))} />
        <KpiCard label="Products with holders" value={String(num(k.products_held))} />
        <KpiCard label="Avg products / customer" value={num(k.avg_products).toFixed(1)} />
        <KpiCard label="Categories" value={String(cats.length)} />
      </KpiRow>

      <Insight>
        <b>{cats.length}</b> product categories spanning deposits-i, financing-i, cards-i, wealth, Takaful, estate and
        digital. <b>{topCat?.category}</b> has the widest reach ({num(topCat?.holders).toLocaleString()} holders);
        customers hold <b>{num(k.avg_products).toFixed(1)}</b> products on average — headroom for deepening relationships.
      </Insight>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Reach by category (unique holders)"
          caption={<><b>{topCat?.category}</b> reaches <b>{num(topCat?.holders).toLocaleString()}</b> customers while wealth, Takaful & estate reach far fewer — these low-reach categories are the highest-margin cross-sell frontier.</>}>
          <VBars data={data.byCategory} xKey="category" valueKey="holders" />
        </ChartCard>
        <ChartCard title="Products held per customer"
          caption={<><b>{shallow.toLocaleString()}</b> customers hold ≤2 products vs an avg of <b>{num(k.avg_products).toFixed(1)}</b> — deepening these shallow relationships is the fastest route to higher per-customer value.</>}>
          <VBars data={data.perCustomer} xKey="products" valueKey="customers" />
        </ChartCard>
      </div>

      <Card className="p-5">
        <h3 className="mb-1 text-sm font-semibold">Cross-sell whitespace — lowest-penetration products</h3>
        <p className="mb-3 text-xs text-muted-foreground">Eligible products with the fewest holders — the clearest campaign targets.</p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {whitespace.map((p) => (
            <div key={p.product_code} className="rounded-lg border bg-muted/30 p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">{p.product_name}</span>
                <Badge variant="muted">{((num(p.holders) / TOTAL) * 100).toFixed(0)}%</Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{p.category} · {p.islamic_contract}</p>
            </div>
          ))}
        </div>
      </Card>

      {cats.map((cat) => {
        const items = data.catalog.filter((p) => p.category === cat);
        return (
          <Card key={cat} className="overflow-hidden p-0">
            <h3 className="border-b bg-muted/40 px-4 py-2.5 text-sm font-semibold">{cat}</h3>
            <table className="w-full text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left">Product</th>
                  <th className="px-4 py-2 text-left">Islamic contract</th>
                  <th className="px-4 py-2 text-right">Indicative rate</th>
                  <th className="px-4 py-2 text-right">Holders</th>
                  <th className="px-4 py-2 text-right">Penetration</th>
                </tr>
              </thead>
              <tbody>
                {items.map((p) => (
                  <tr key={p.product_code} className="border-t">
                    <td className="px-4 py-2 font-medium">{p.product_name}</td>
                    <td className="px-4 py-2"><Badge variant="muted">{p.islamic_contract}</Badge></td>
                    <td className="px-4 py-2 text-right tabular-nums">{num(p.indicative_rate) > 0 ? `${num(p.indicative_rate).toFixed(2)}%` : "—"}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{num(p.holders).toLocaleString()}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">{((num(p.holders) / TOTAL) * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        );
      })}
    </div>
  );
}
