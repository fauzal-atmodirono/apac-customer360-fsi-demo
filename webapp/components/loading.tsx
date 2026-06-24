import { Skeleton } from "@/components/ui/skeleton";

export function PageSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-64" />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-72" />)}
      </div>
    </div>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  return (
    <div className="rounded-lg border border-danger/30 bg-danger/5 p-6 text-sm">
      <p className="font-semibold text-danger">Failed to load data</p>
      <pre className="mt-2 whitespace-pre-wrap text-xs text-muted-foreground">{String(error)}</pre>
      <p className="mt-2 text-xs text-muted-foreground">Check that ADC is set and the BigQuery datasets exist.</p>
    </div>
  );
}
