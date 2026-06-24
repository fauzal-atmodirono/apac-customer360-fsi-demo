import { Card } from "@/components/ui/card";

type Col = { key: string; label: string; fmt?: (v: unknown, row: Record<string, unknown>) => React.ReactNode; align?: "left" | "right" };

export function DataTable({ title, columns, rows }: { title: string; columns: Col[]; rows: Record<string, unknown>[] }) {
  return (
    <Card className="p-5">
      <h3 className="mb-3 text-sm font-semibold tracking-tight">{title}</h3>
      <div className="max-h-80 overflow-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-muted/70 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              {columns.map((c) => (
                <th key={c.key} className={`px-3 py-2 font-medium ${c.align === "right" ? "text-right" : "text-left"}`}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t hover:bg-muted/40">
                {columns.map((c) => (
                  <td key={c.key} className={`px-3 py-1.5 ${c.align === "right" ? "text-right tabular-nums" : ""}`}>
                    {c.fmt ? c.fmt(r[c.key], r) : String(r[c.key] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
