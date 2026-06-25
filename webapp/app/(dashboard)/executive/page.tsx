"use client";

import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, VBars, Histogram, GroupedBars, HBars, MultiLine, Donut } from "@/components/charts";
import { SEGMENT_COLORS } from "@/lib/colors";
import { money, num } from "@/lib/format";

type Exec = {
  kpis: Record<string, number>;
  growth: Record<string, number | null>;
  segments: { segment: string; customers: number; avg_savings: number; avg_card_spend: number }[];
  age: { age: number; segment: string }[];
  tier: { tier: string; segment: string; customers: number }[];
  portfolio: { pool: string; amount: number }[];
  metrics: Record<string, number | null>;
  aumTrend: { month: string; savings: number; deposits: number }[];
};

function MetricGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{title}</h2>
      <KpiRow>{children}</KpiRow>
    </div>
  );
}

export default function ExecutivePage() {
  const { data, error, isLoading } = useApi<Exec>("executive");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const k = data.kpis;
  const gr = data.growth;
  const top = [...data.segments].sort((a, b) => b.customers - a.customers)[0];
  const total = num(k.customers);
  const relationship = num(k.total_savings) + num(k.total_deposit);
  const sav = num(data.portfolio.find((p) => p.pool === "Savings")?.amount);
  const loan = num(data.portfolio.find((p) => p.pool === "Loans")?.amount);
  // derived executive figures
  const segAum = data.segments.map((s) => ({ seg: s.segment, customers: num(s.customers), aum: num(s.avg_savings) * num(s.customers) }));
  const totalAum = segAum.reduce((a, s) => a + s.aum, 0) || 1;
  const mass = segAum.find((s) => s.seg === "STANDARD_RETAIL");
  const massCustPct = mass ? (mass.customers / total) * 100 : 0;
  const massAumPct = mass ? (mass.aum / totalAum) * 100 : 0;
  const primeShare = data.age.filter((a) => num(a.age) >= 30 && num(a.age) < 60).length / (data.age.length || 1) * 100;
  const hnwAff = data.tier.filter((t) => ["HNW", "AFFLUENT"].includes(t.tier)).reduce((a, t) => a + num(t.customers), 0);
  const deployPct = (loan / (sav || 1)) * 100;
  const m = data.metrics;
  const aumFlow = data.aumTrend.flatMap((t) => [
    { month: t.month, series: "Savings-i", value: num(t.savings) },
    { month: t.month, series: "Deposits-i", value: num(t.deposits) },
  ]);
  const aumLatest = data.aumTrend[data.aumTrend.length - 1];
  const aumPrev = data.aumTrend[data.aumTrend.length - 2];
  const aumMoM = aumLatest && aumPrev
    ? (((num(aumLatest.savings) + num(aumLatest.deposits)) - (num(aumPrev.savings) + num(aumPrev.deposits))) / ((num(aumPrev.savings) + num(aumPrev.deposits)) || 1)) * 100
    : null;
  const income = [
    { source: "Profit income", amount: num(m.profit_paid) },
    { source: "Fee income", amount: num(m.fee_income) },
  ];
  const profitShare = (num(m.profit_paid) / ((num(m.profit_paid) + num(m.fee_income)) || 1)) * 100;

  return (
    <div className="space-y-5">
      <PageHeader title="Executive overview" />
      <KpiRow>
        <KpiCard label="Customers" value={total.toLocaleString()} delta={gr.customers} />
        <KpiCard label="Total savings-i" value={money(k.total_savings)} delta={gr.total_savings} />
        <KpiCard label="Total financing-i" value={money(k.total_loans)} delta={gr.total_loans} />
        <KpiCard label="Avg propensity" value={`${num(k.avg_ips).toFixed(0)}/100`} delta={gr.avg_ips} />
      </KpiRow>
      <KpiRow>
        <KpiCard label="Avg age" value={num(k.avg_age).toFixed(0)} />
        <KpiCard label="Home-financing holders" value={`${(num(k.pct_mortgage) * 100).toFixed(0)}%`} delta={gr.pct_mortgage} />
        <KpiCard label="30-day card spend" value={money(k.total_card_spend)} delta={gr.total_card_spend} />
        <KpiCard label="Financing-to-savings" value={num(k.ltv).toFixed(2)} delta={gr.ltv} />
      </KpiRow>

      <Insight>
        <b>{top.customers} of {total}</b> customers are <b>{top.segment}</b>. Total relationship balances
        (savings + deposits) are <b>{money(relationship)}</b>, with <b>{(num(k.pct_mortgage) * 100).toFixed(0)}%</b> holding a mortgage.
      </Insight>

      <MetricGroup title="Franchise & relationship">
        <KpiCard label="AUM (relationship balances)" value={money(m.aum)} accent="success" />
        <KpiCard label="Avg products / customer" value={num(m.avg_products).toFixed(1)} />
        <KpiCard label="Primary-bank share" value={`${(num(m.primary_bank) * 100).toFixed(0)}%`} sub="salary-credited" />
        <KpiCard label="Avg financial wellness" value={`${num(m.avg_wellness).toFixed(0)}/100`} />
      </MetricGroup>

      <MetricGroup title="Asset quality & risk">
        <KpiCard label="NPF rate" value={`${(num(m.npf_rate) * 100).toFixed(1)}%`} accent="danger" />
        <KpiCard label="Total arrears" value={money(m.arrears)} accent="danger" />
        <KpiCard label="At-risk customers" value={num(m.at_risk).toLocaleString()} accent="danger" />
        <KpiCard label="Deposits at risk" value={money(m.at_risk_dollars)} accent="danger" sub="HIGH/MED churn" />
      </MetricGroup>

      <MetricGroup title="Revenue & returns">
        <KpiCard label="Shariah profit paid" value={money(m.profit_paid)} />
        <KpiCard label="Transfer fee income" value={money(m.fee_income)} />
        <KpiCard label="Avg effective yield" value={`${num(m.avg_yield).toFixed(2)}%`} />
        <KpiCard label="Campaign conversion" value={`${(num(m.conv_rate) * 100).toFixed(1)}%`} />
      </MetricGroup>

      <MetricGroup title="Engagement & growth">
        <KpiCard label="Self-service ratio" value={`${(num(m.digital_ratio) * 100).toFixed(0)}%`} sub="ATM/CDM vs branch" />
        <KpiCard label="AUM MoM growth" value={aumMoM != null ? `${aumMoM >= 0 ? "+" : ""}${aumMoM.toFixed(1)}%` : "—"} accent={aumMoM != null && aumMoM >= 0 ? "success" : "default"} />
        <KpiCard label="30-day card spend" value={money(k.total_card_spend)} delta={gr.total_card_spend} />
        <KpiCard label="Customers" value={total.toLocaleString()} delta={gr.customers} />
      </MetricGroup>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="AUM trend — savings vs deposits (monthly)"
          caption={aumMoM != null ? <>Relationship balances grew <b>{aumMoM >= 0 ? "+" : ""}{aumMoM.toFixed(1)}%</b> month-on-month to <b>{money(m.aum)}</b> — a low-cost funding base expanding faster than the financing book; deploy into financing & wealth-i.</> : <>Monthly savings-i vs deposits-i balances.</>}>
          <MultiLine data={aumFlow} indexKey="month" seriesKey="series" valueKey="value"
            colorMap={{ "Savings-i": "#1565C0", "Deposits-i": "#26A69A" }} height={300} />
        </ChartCard>
        <ChartCard title="Income contribution"
          caption={<>Shariah profit income is <b>{profitShare.toFixed(0)}%</b> of this view (<b>{money(m.profit_paid)}</b>) vs <b>{money(m.fee_income)}</b> fee income — grow fee-based revenue (transfers, cards, advisory) to diversify earnings.</>}>
          <Donut data={income} nameKey="source" valueKey="amount" colorMap={{ "Profit income": "#1565C0", "Fee income": "#F9A825" }} />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Customers by propensity segment"
          caption={<><b>{mass?.seg ?? "STANDARD_RETAIL"}</b> is <b>{massCustPct.toFixed(0)}%</b> of customers but holds only <b>{massAumPct.toFixed(0)}%</b> of est. AUM — the investor/affluent segments punch well above their weight; migrating mass-retail upward is the single biggest AUM lever.</>}>
          <VBars data={data.segments} xKey="segment" valueKey="customers" colorKey="segment" colorMap={SEGMENT_COLORS} />
        </ChartCard>
        <ChartCard title="Age distribution"
          caption={<><b>{primeShare.toFixed(0)}%</b> of customers are aged 30–59 (avg <b>{num(k.avg_age).toFixed(0)}</b>) — peak demand for home, education and retirement financing; target life-stage journeys here.</>}>
          <Histogram data={data.age} valueKey="age" refLine={num(k.avg_age)} />
        </ChartCard>
        <ChartCard title="Tier × propensity segment"
          caption={<><b>{hnwAff.toLocaleString()}</b> customers sit in HNW/AFFLUENT tiers — where the investor & digital-shopper segments concentrate; prioritise wealth, advisory and premium-card cross-sell there.</>}>
          <GroupedBars data={data.tier} xKey="tier" seriesKey="segment" valueKey="customers" colorMap={SEGMENT_COLORS} />
        </ChartCard>
        <ChartCard title="Portfolio composition"
          caption={<>Deposit-rich <b>{(sav / (loan || 1)).toFixed(1)}:1</b> savings-to-financing book — only <b>{deployPct.toFixed(0)}%</b> of savings is deployed as financing, signalling ample low-cost funding to grow the financing book.</>}>
          <HBars data={data.portfolio} yKey="pool" valueKey="amount" />
        </ChartCard>
      </div>
    </div>
  );
}
