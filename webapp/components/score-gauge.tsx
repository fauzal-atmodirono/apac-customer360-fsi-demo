"use client";

import { ResponsiveContainer, RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";

export function ScoreGauge({
  value, label, color = "#1565C0", suffix = "/100", max = 100,
}: { value: number; label: string; color?: string; suffix?: string; max?: number }) {
  const data = [{ value: Math.max(0, Math.min(max, value)) }];
  return (
    <div className="relative flex flex-col items-center">
      <ResponsiveContainer width="100%" height={150}>
        <RadialBarChart
          innerRadius="72%" outerRadius="100%" data={data}
          startAngle={210} endAngle={-30} barSize={14}
        >
          <PolarAngleAxis type="number" domain={[0, max]} tick={false} />
          <RadialBar dataKey="value" cornerRadius={8} fill={color} background={{ fill: "#eef2f7" }} isAnimationActive={false} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pt-3">
        <span className="text-2xl font-semibold tracking-tight" style={{ color }}>{Math.round(value)}</span>
        <span className="text-[11px] text-muted-foreground">{suffix}</span>
      </div>
      <p className="mt-1 text-xs font-medium text-muted-foreground">{label}</p>
    </div>
  );
}
