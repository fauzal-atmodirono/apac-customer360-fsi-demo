import { NextResponse } from "next/server";
import { botGet } from "@/lib/bot";
import { collectibilityForCifs } from "@/lib/queries";

export const dynamic = "force-dynamic";

type Contact = { customer_id: string; name: string; dpd_stage: string; channels: string[] };
type Summary = {
  contacted: boolean; replied: boolean; last_contact_at: string | null;
  last_channel: string | null; last_intent: string | null; last_outcome: string | null;
  active_ptp: Ptp | null; active_restructure: Restructure | null;
};
type Ptp = {
  id: string; customer_id: string; conversation_id: string | null;
  promise_date: string; amount: number | null; status: string; source: string;
  created_at: string; updated_at: string;
};
type Restructure = {
  id: string; customer_id: string; conversation_id: string | null;
  note: string | null; new_installment: number | null; status: string; source: string;
  created_at: string; updated_at: string;
};

// Fallback when BigQuery has no financing row for a demo contact: derive the class
// from the contact's configured tone stage (bands in dataform/includes/constants.js;
// mirrors the bot's own dpd_stage fallback in /start).
const STAGE_KOL: Record<string, { collectibility: number; label: string }> = {
  SOFT_REMINDER: { collectibility: 2, label: "Kol-2 Special Mention" },
  INTENSIVE: { collectibility: 2, label: "Kol-2 Special Mention" },
  FIELD_VISIT: { collectibility: 2, label: "Kol-2 Special Mention" },
  RECOVERY_LEGAL: { collectibility: 3, label: "Kol-3 Substandard" },
};

export async function GET() {
  try {
    const [contacts, summary, ptps, restructures] = await Promise.all([
      botGet<Contact[]>("contacts"),
      botGet<Record<string, Summary>>("outreach-summary"),
      botGet<Ptp[]>("ptps"), // newest first; the bot sweeps past-due -> BROKEN on read
      botGet<Restructure[]>("restructures"), // newest first
    ]);

    let financing: Awaited<ReturnType<typeof collectibilityForCifs>> = [];
    try {
      financing = await collectibilityForCifs(contacts.map((c) => c.customer_id));
    } catch {
      // BigQuery unreachable (bare local demo) -> every row uses the stage fallback.
    }
    const finByCif = new Map(financing.map((r) => [r.customer_id, r]));
    const latestPtp = new Map<string, Ptp>();
    for (const p of ptps) if (!latestPtp.has(p.customer_id)) latestPtp.set(p.customer_id, p);
    const latestRestructure = new Map<string, Restructure>();
    for (const rs of restructures) if (!latestRestructure.has(rs.customer_id)) latestRestructure.set(rs.customer_id, rs);

    const rows = contacts.map((c) => {
      const fin = finByCif.get(c.customer_id);
      const s = summary[c.customer_id];
      const ptp = latestPtp.get(c.customer_id) ?? null;
      const restructure = latestRestructure.get(c.customer_id) ?? null;
      const fallback = STAGE_KOL[c.dpd_stage] ?? STAGE_KOL.SOFT_REMINDER;
      return {
        customer_id: c.customer_id,
        name: c.name,
        dpd_stage: c.dpd_stage,
        channels: c.channels,
        current_dpd: fin?.current_dpd ?? null,
        collectibility: fin?.collectibility ?? fallback.collectibility,
        collectibility_label: fin?.collectibility_label ?? fallback.label,
        total_arrears: fin?.total_arrears ?? null,
        collectibility_source: fin ? "bigquery" : "fallback",
        contacted: s?.contacted ?? false,
        replied: s?.replied ?? false,
        last_contact_at: s?.last_contact_at ?? null,
        last_channel: s?.last_channel ?? null,
        last_intent: s?.last_intent ?? null,
        last_outcome: s?.last_outcome ?? null,
        ptp, // latest PTP in any status, for the chip
        restructure, // latest restructure in any status, for the chip
        suppressed: ptp?.status === "ACTIVE" || restructure?.status === "ACTIVE",
      };
    });
    return NextResponse.json({ rows });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
