"use client";

import { useApi } from "@/components/data";
import { PageSkeleton, ErrorState } from "@/components/loading";
import { PageHeader, Insight } from "@/components/insight";
import { KpiCard, KpiRow } from "@/components/kpi-card";
import { ChartCard, MultiLine, StackArea, VBars, Donut } from "@/components/charts";
import { CHANNEL_COLORS } from "@/lib/colors";
import { money, num } from "@/lib/format";

type Trends = {
  daily: { txn_date: string; channel: string; spend: number }[];
  weekly: { week: string; category: string; spend: number }[];
  atm: { week: string; withdrawals: number; amount: number }[];
  byTimeOfDay: { time_of_day: string; txns: number; spend: number }[];
  byHour: { hour: number; txns: number; spend: number }[];
  byDayGroup: { day_group: string; txns: number; spend: number; active_days: number }[];
  byDayOfWeek: { day_of_week: string; dow_num: number; txns: number; spend: number }[];
};

const TOD_ORDER = ["Midnight", "Early morning", "Morning", "Noon", "Afternoon", "Evening", "Night"];
const DAYGROUP_COLORS = { Weekday: "#1565C0", Weekend: "#F9A825" };
const fmtHour = (h: number) => {
  const ap = h < 12 ? "am" : "pm";
  const hr = h % 12 === 0 ? 12 : h % 12;
  return `${hr} ${ap}`;
};

export default function TrendsPage() {
  const { data, error, isLoading } = useApi<Trends>("trends");
  if (error) return <ErrorState error={error} />;
  if (isLoading || !data) return <PageSkeleton />;

  const totalSpend = data.daily.reduce((s, d) => s + num(d.spend), 0);
  const credit = data.daily.filter((d) => d.channel === "Credit").reduce((s, d) => s + num(d.spend), 0);
  const catTotals = new Map<string, number>();
  for (const w of data.weekly) catTotals.set(w.category, (catTotals.get(w.category) ?? 0) + num(w.spend));
  const topCat = [...catTotals.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—";
  const peakAtm = Math.max(...data.atm.map((a) => num(a.withdrawals)), 0);

  // --- transaction timing ---
  const tod = [...data.byTimeOfDay].sort((a, b) => TOD_ORDER.indexOf(a.time_of_day) - TOD_ORDER.indexOf(b.time_of_day));
  const hours = [...data.byHour].map((h) => ({ ...h, label: fmtHour(num(h.hour)) }));
  const peakHour = [...data.byHour].sort((a, b) => num(b.txns) - num(a.txns))[0];
  const busiestTod = [...data.byTimeOfDay].sort((a, b) => num(b.txns) - num(a.txns))[0];
  const perDay = (g?: { txns: number; active_days: number }) => (g && num(g.active_days) ? num(g.txns) / num(g.active_days) : 0);
  const wkday = data.byDayGroup.find((d) => d.day_group === "Weekday");
  const wkend = data.byDayGroup.find((d) => d.day_group === "Weekend");
  const wkdayPerDay = perDay(wkday);
  const wkendPerDay = perDay(wkend);
  const busiestDow = [...data.byDayOfWeek].sort((a, b) => num(b.txns) - num(a.txns))[0];

  return (
    <div className="space-y-5">
      <PageHeader title="Spend & transaction trends" subtitle="Card-transaction facts over the trailing 90 days (credit + debit purchases)." />
      <KpiRow>
        <KpiCard label="90-day spend" value={money(totalSpend)} />
        <KpiCard label="Credit share" value={`${((credit / (totalSpend || 1)) * 100).toFixed(0)}%`} />
        <KpiCard label="Top category" value={topCat} />
        <KpiCard label="Peak ATM / week" value={String(peakAtm)} />
      </KpiRow>

      <Insight>
        Customers spent <b>{money(totalSpend)}</b> on cards in 90 days — <b>{((credit / (totalSpend || 1)) * 100).toFixed(0)}%</b> credit
        / <b>{(((totalSpend - credit) / (totalSpend || 1)) * 100).toFixed(0)}%</b> debit. <b>{topCat}</b> is the largest category by value.
      </Insight>

      <ChartCard title="Daily spend — credit vs debit"
        caption={<>Credit consistently outpaces debit — the primary rail to build rewards/limit strategies around.</>}>
        <MultiLine data={data.daily} indexKey="txn_date" seriesKey="channel" valueKey="spend" colorMap={CHANNEL_COLORS} height={320} />
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Weekly category mix"
          caption={<><b>{topCat}</b> leads weekly card value; the mix is stable week-to-week.</>}>
          <StackArea data={data.weekly} indexKey="week" seriesKey="category" valueKey="spend" />
        </ChartCard>
        <ChartCard title="ATM withdrawals per week"
          caption={<>ATM use peaks at <b>{peakAtm}</b> withdrawals in a week — rising cash-out is an early churn cue.</>}>
          <VBars data={data.atm} xKey="week" valueKey="withdrawals" color="#C62828" />
        </ChartCard>
      </div>

      {/* ---- Transaction timing ---- */}
      <div className="pt-2">
        <h2 className="text-lg font-semibold tracking-tight">Transaction timing</h2>
        <p className="text-sm text-muted-foreground">When customers transact — by hour, daypart, day of week, and weekday vs weekend (90-day card purchases).</p>
      </div>
      <KpiRow>
        <KpiCard label="Peak hour" value={peakHour ? fmtHour(num(peakHour.hour)) : "—"} sub={peakHour ? `${num(peakHour.txns).toLocaleString()} txns` : undefined} />
        <KpiCard label="Busiest daypart" value={busiestTod?.time_of_day ?? "—"} sub={busiestTod ? `${num(busiestTod.txns).toLocaleString()} txns` : undefined} />
        <KpiCard label="Busiest day" value={busiestDow?.day_of_week ?? "—"} sub={busiestDow ? `${num(busiestDow.txns).toLocaleString()} txns` : undefined} />
        <KpiCard label="Weekend vs weekday" value={`${wkdayPerDay ? (wkendPerDay / wkdayPerDay * 100).toFixed(0) : 0}%`} sub="per-day txn rate" />
      </KpiRow>

      <Insight>
        Activity peaks at <b>{peakHour ? fmtHour(num(peakHour.hour)) : "—"}</b> and the <b>{busiestTod?.time_of_day}</b> daypart.
        Weekends run <b>{wkendPerDay.toFixed(0)}</b> txns/day vs <b>{wkdayPerDay.toFixed(0)}</b> on weekdays
        ({wkdayPerDay && wkendPerDay < wkdayPerDay ? "lighter" : "heavier"} per day) — time campaigns and staffing to the live windows.
      </Insight>

      <ChartCard title="Transactions by hour of day"
        caption={<>Card activity ramps from morning, peaks around <b>{peakHour ? fmtHour(num(peakHour.hour)) : "midday"}</b>, and tapers overnight.</>}>
        <VBars data={hours} xKey="label" valueKey="txns" height={300} />
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Transactions by daypart"
          caption={<><b>{busiestTod?.time_of_day}</b> is the busiest window — prioritise notifications and offers then.</>}>
          <VBars data={tod} xKey="time_of_day" valueKey="txns" />
        </ChartCard>
        <ChartCard title="Weekday vs weekend"
          caption={<>Per active day: <b>{wkdayPerDay.toFixed(0)}</b> weekday vs <b>{wkendPerDay.toFixed(0)}</b> weekend txns — totals below reflect 5 vs 2 days.</>}>
          <Donut data={data.byDayGroup} nameKey="day_group" valueKey="txns" colorMap={DAYGROUP_COLORS} />
        </ChartCard>
      </div>

      <ChartCard title="Transactions by day of week"
        caption={<><b>{busiestDow?.day_of_week}</b> sees the most card activity across the week.</>}>
        <VBars data={data.byDayOfWeek} xKey="day_of_week" valueKey="txns" />
      </ChartCard>
    </div>
  );
}
