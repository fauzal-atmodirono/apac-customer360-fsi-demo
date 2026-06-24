import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function KpiCard({
  label, value, sub, accent, delta, deltaLabel = "vs last 30 days",
}: {
  label: string; value: string; sub?: string;
  accent?: "default" | "danger" | "success";
  delta?: number | null; deltaLabel?: string;
}) {
  const up = (delta ?? 0) >= 0;
  return (
    <Card className="p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn(
        "mt-2 text-3xl font-semibold tracking-tight",
        accent === "danger" && "text-danger",
        accent === "success" && "text-success",
      )}>{value}</p>
      {delta != null ? (
        <p className="mt-1.5 flex items-center gap-1 text-xs">
          <span className={cn("inline-flex items-center gap-0.5 font-semibold", up ? "text-success" : "text-danger")}>
            {up ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
            {up ? "+" : ""}{delta.toFixed(1)}%
          </span>
          <span className="text-muted-foreground">{deltaLabel}</span>
        </p>
      ) : sub ? (
        <p className="mt-1 text-xs text-muted-foreground">{sub}</p>
      ) : null}
    </Card>
  );
}

export function KpiRow({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{children}</div>;
}
