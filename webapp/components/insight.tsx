import { Lightbulb } from "lucide-react";
import { cn } from "@/lib/utils";

export function Insight({
  children, tone = "info",
}: { children: React.ReactNode; tone?: "info" | "success" | "warning" }) {
  return (
    <div className={cn(
      "flex items-start gap-2 rounded-lg border px-4 py-3 text-sm",
      tone === "info" && "border-primary/20 bg-accent text-accent-foreground",
      tone === "success" && "border-success/20 bg-success/5 text-foreground",
      tone === "warning" && "border-warning/30 bg-warning/10 text-foreground",
    )}>
      <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
      <p className="[&_b]:font-semibold">{children}</p>
    </div>
  );
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-5">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
    </div>
  );
}
