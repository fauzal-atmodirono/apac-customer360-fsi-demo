"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Sparkles, MapPin, CalendarClock, Wallet } from "lucide-react";
import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ScoreGauge } from "@/components/score-gauge";
import { ChartCard, MultiLine, Donut } from "@/components/charts";
import { DataTable } from "@/components/data-table";
import { SEGMENT_COLORS, CHANNEL_COLORS, CHURN_COLORS } from "@/lib/colors";
import { money, num } from "@/lib/format";

type Detail = {
  profile: Record<string, string | number | boolean | null>;
  accounts: Record<string, unknown>[];
  loans: Record<string, unknown>[];
  trend: { week: string; channel: string; spend: number }[];
  categories: { category: string; spend: number }[];
  recent: Record<string, unknown>[];
  signals: Record<string, string | number | null> | null;
  nba: { title: string; reason: string; priority: "High" | "Medium" | "Low" }[];
};
const churnVariant = (b: string) => (b === "HIGH" ? "danger" : b === "MEDIUM" ? "warning" : "success");

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold tabular-nums">{value}</span>
    </div>
  );
}

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, isLoading } = useApi<Detail>(`customers/${id}`);
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const p = data.profile;
  const savings = num(p.total_savings_balance);
  const deposits = num(p.total_deposit_balance);
  const loans = num(p.total_loan_outstanding);
  const net = savings + deposits - loans;
  const seg = String(p.propensity_score_segment);
  const churn = String(p.churn_risk_segment);
  const s = data.signals;
  const nbp = s ? [
    { product: "Mortgage", score: num(s.p_mortgage) },
    { product: "Term deposit", score: num(s.p_term_deposit) },
    { product: "Premium card", score: num(s.p_card_upgrade) },
    { product: "Investment", score: num(s.p_investment) },
    { product: "Debt consolidation", score: num(s.p_consolidation) },
  ].sort((a, b) => b.score - a.score) : [];

  return (
    <div className="space-y-5">
      <Link href="/customers" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> All customers
      </Link>

      {/* Header */}
      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{String(p.full_name)}</h1>
            <p className="mt-0.5 font-mono text-xs text-muted-foreground">CIF {String(p.customer_id)} · {String(p.phone_number)}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{String(p.region)}</span>
              <span>·</span><span>{num(p.age)} yrs</span>
              <span>·</span><span className="inline-flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5" />{num(p.tenure_years)}y tenure</span>
              <span>·</span><span className="inline-flex items-center gap-1"><Wallet className="h-3.5 w-3.5" />{String(p.income_band)} income</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium">
              <span className="h-2 w-2 rounded-full" style={{ background: SEGMENT_COLORS[seg] ?? "#94A3B8" }} />{seg}
            </span>
            <Badge variant={churnVariant(churn)}>Churn: {churn}</Badge>
            <Badge variant="muted">{String(p.customer_segment)}</Badge>
          </div>
        </div>
      </Card>

      {/* Relationship value */}
      <KpiRow>
        <KpiCard label="Total savings" value={money(savings)} />
        <KpiCard label="Total deposits" value={money(deposits)} />
        <KpiCard label="Loans outstanding" value={money(loans)} />
        <KpiCard label="Net position" value={money(net)} accent={net >= 0 ? "success" : "danger"} />
      </KpiRow>

      {/* Scores + spend snapshot */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5">
          <h3 className="mb-2 text-sm font-semibold">Investment propensity</h3>
          <ScoreGauge value={num(p.investment_propensity_score)} label="likelihood to invest" color="#2E7D32" />
        </Card>
        <Card className="p-5">
          <h3 className="mb-2 text-sm font-semibold">Churn risk</h3>
          <ScoreGauge value={num(p.churn_risk_score)} label={`band: ${churn}`} color={CHURN_COLORS[churn] ?? "#F9A825"} />
        </Card>
        <Card className="flex flex-col justify-center gap-3 p-5">
          <div className="flex items-center justify-between text-sm"><span className="text-muted-foreground">Debt-to-deposit</span><span className="font-semibold">{num(p.debt_to_deposit_ratio).toFixed(2)}</span></div>
          <div className="flex items-center justify-between text-sm"><span className="text-muted-foreground">30-day card spend</span><span className="font-semibold">{money(p.total_card_spend_last_30_days)}</span></div>
          <div className="flex items-center justify-between text-sm"><span className="text-muted-foreground">ATM withdrawals (30d)</span><span className="font-semibold">{num(p.atm_withdrawals_last_30_days)}</span></div>
          <div className="flex items-center justify-between text-sm"><span className="text-muted-foreground">Top category</span><span className="font-semibold">{String(p.top_spending_category)}</span></div>
          <div className="flex items-center justify-between text-sm"><span className="text-muted-foreground">Active mortgage</span><span className="font-semibold">{p.has_active_mortgage ? "Yes" : "No"}</span></div>
        </Card>
      </div>

      {/* Personalization signals + Next-Best-Product */}
      {s && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="p-5 lg:col-span-2">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Sparkles className="h-4 w-4 text-primary" /> Personalization signals</h3>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="muted">RFM: {String(s.rfm_segment)}</Badge>
              <Badge variant="muted">{String(s.life_stage)}</Badge>
              <Badge variant={String(s.financial_health_band) === "Stretched" ? "danger" : String(s.financial_health_band) === "Moderate" ? "warning" : "success"}>
                Health: {String(s.financial_health_band)}
              </Badge>
              <Badge variant="muted">Active: {String(s.preferred_time_of_day)}</Badge>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
              <Stat label="Share-of-wallet" value={`${(num(s.share_of_wallet) * 100).toFixed(0)}%`} />
              <Stat label="Liquidity buffer" value={`${num(s.liquidity_buffer_months).toFixed(1)} mo`} />
              <Stat label="Debt-service ratio" value={num(s.debt_service_ratio).toFixed(2)} />
              <Stat label="Spend velocity" value={`${num(s.spend_velocity_pct) >= 0 ? "+" : ""}${num(s.spend_velocity_pct).toFixed(0)}%`} />
              <Stat label="Avg ticket" value={money(s.avg_ticket)} />
              <Stat label="Discretionary" value={`${(num(s.discretionary_ratio) * 100).toFixed(0)}%`} />
              <Stat label="Recency" value={`${num(s.recency_days)}d`} />
              <Stat label="Frequency (90d)" value={String(num(s.frequency_90d))} />
              <Stat label="Categories" value={String(num(s.distinct_categories))} />
            </div>
          </Card>
          <Card className="p-5">
            <h3 className="mb-1 text-sm font-semibold">Next-Best-Product</h3>
            <p className="mb-3 text-xs text-muted-foreground">Propensity score (0–100) per product.</p>
            <div className="space-y-2.5">
              {nbp.map((n, i) => (
                <div key={n.product}>
                  <div className="flex items-center justify-between text-xs">
                    <span className={i === 0 ? "font-semibold" : ""}>{n.product}{i === 0 && <Badge variant="success" className="ml-1.5">Top</Badge>}</span>
                    <span className="tabular-nums text-muted-foreground">{n.score}</span>
                  </div>
                  <div className="mt-1 h-2 rounded-full bg-muted">
                    <div className="h-2 rounded-full" style={{ width: `${n.score}%`, background: i === 0 ? "#1565C0" : "#90CAF9" }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* Products */}
      <div className="grid gap-4 lg:grid-cols-2">
        <DataTable title={`Accounts (${data.accounts.length})`} rows={data.accounts}
          columns={[
            { key: "account_id", label: "Account" },
            { key: "account_type", label: "Type" },
            { key: "balance", label: "Balance", align: "right", fmt: (v) => money(v as number) },
            { key: "status_desc", label: "Status" },
            { key: "open_date", label: "Opened" },
          ]} />
        <DataTable title={`Loans (${data.loans.length})`} rows={data.loans}
          columns={[
            { key: "loan_type", label: "Type" },
            { key: "outstanding", label: "Outstanding", align: "right", fmt: (v) => money(v as number) },
            { key: "monthly", label: "Monthly", align: "right", fmt: (v) => money(v as number) },
            { key: "next_due", label: "Next due" },
          ]} />
      </div>

      {/* Spending */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Spend trend (90d, weekly)">
          {data.trend.length
            ? <MultiLine data={data.trend} indexKey="week" seriesKey="channel" valueKey="spend" colorMap={CHANNEL_COLORS} />
            : <p className="py-12 text-center text-sm text-muted-foreground">No card activity.</p>}
        </ChartCard>
        <ChartCard title="Category mix (90d)">
          {data.categories.length
            ? <Donut data={data.categories} nameKey="category" valueKey="spend" />
            : <p className="py-12 text-center text-sm text-muted-foreground">No card activity.</p>}
        </ChartCard>
      </div>

      <DataTable title="Recent transactions" rows={data.recent}
        columns={[
          { key: "date", label: "Date" },
          { key: "channel", label: "Channel" },
          { key: "category", label: "Category" },
          { key: "type", label: "Type" },
          { key: "amount", label: "Amount", align: "right", fmt: (v) => money(v as number) },
        ]} />
    </div>
  );
}
