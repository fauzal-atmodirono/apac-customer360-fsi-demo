"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  Radio, Loader2, MessageSquare, AlertTriangle, Check, Minus, Lock, Send,
  CalendarClock, X, FileText,
} from "lucide-react";
import { PageHeader } from "@/components/insight";
import { Card } from "@/components/ui/card";

type Ptp = {
  id: string; customer_id: string; promise_date: string; amount: number | null;
  status: string; source: string;
};
type Restructure = {
  id: string; customer_id: string; note: string | null; new_installment: number | null;
  status: string; source: string;
};
type Row = {
  customer_id: string; name: string; dpd_stage: string; channels: string[];
  current_dpd: number | null; collectibility: number; collectibility_label: string;
  total_arrears: number | null; collectibility_source: string;
  contacted: boolean; replied: boolean; last_contact_at: string | null;
  last_channel: string | null; last_intent: string | null; last_outcome: string | null;
  ptp: Ptp | null; restructure: Restructure | null; suppressed: boolean;
};
type Message = { direction: string; channel: string; body: string; status: string; ts: string };
type Conversation = {
  id: string; customer_id: string; channel: string; dpd: number; stage: string;
  tone: string; language: string; detected_intent: string | null; outcome: string;
  messages: Message[];
};

const fetcher = (u: string) => fetch(u).then((r) => r.json());

const OUTCOME_STYLE: Record<string, string> = {
  OPENED: "bg-muted text-foreground",
  PTP_OBTAINED: "bg-amber-100 text-amber-900",
  RESTRUCTURE_OFFERED: "bg-emerald-100 text-emerald-900",
  HOSTILE_ESCALATED: "bg-red-100 text-red-900",
  NO_RESPONSE: "bg-muted text-muted-foreground",
};

// Kol-1 (Current) .. Kol-5 (Loss) — demo OJK-style bands, see dataform constants.js.
const KOL_STYLE: Record<number, string> = {
  1: "bg-emerald-100 text-emerald-900",
  2: "bg-amber-100 text-amber-900",
  3: "bg-orange-100 text-orange-900",
  4: "bg-red-100 text-red-900",
  5: "bg-red-200 text-red-950",
};

const PTP_STYLE: Record<string, string> = {
  ACTIVE: "bg-amber-100 text-amber-900",
  KEPT: "bg-emerald-100 text-emerald-900",
  BROKEN: "bg-red-100 text-red-900",
  CANCELLED: "bg-muted text-muted-foreground",
};

const RESTRUCTURE_STYLE: Record<string, string> = {
  ACTIVE: "bg-sky-100 text-sky-900",
  ACCEPTED: "bg-emerald-100 text-emerald-900",
  DECLINED: "bg-muted text-muted-foreground",
  CANCELLED: "bg-muted text-muted-foreground",
};

// Actions column: one primary (Send); PTP/Rekon controls are quiet ghost buttons
// grouped under a muted label so Send stays visually dominant.
const GBTN = "rounded px-1.5 py-0.5 text-xs font-medium transition-colors disabled:opacity-40 disabled:hover:bg-transparent";
const GBTN_NEUTRAL = `${GBTN} text-foreground/70 hover:bg-muted`;
const GBTN_POSITIVE = `${GBTN} text-emerald-700 hover:bg-emerald-50`;
const GBTN_MUTED = `${GBTN} text-muted-foreground hover:bg-muted`;
const GROUP_LABEL = "w-11 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground";

function fmtWhen(ts: string | null) {
  if (!ts) return "—";
  const d = new Date(ts);
  return d.toLocaleString("en-MY", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function OutreachPage() {
  const { data: wb, mutate: refreshWb } = useSWR<{ rows: Row[]; error?: string }>(
    "/api/workbench", fetcher, { refreshInterval: 5000 },
  );
  const [channel, setChannel] = useState("whatsapp");
  const [convId, setConvId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null); // customer_id of in-flight action
  const [err, setErr] = useState<string | null>(null);
  const [ptpForm, setPtpForm] = useState<{ cif: string; date: string; amount: string } | null>(null);
  const [rekonForm, setRekonForm] = useState<{ cif: string; note: string; installment: string } | null>(null);

  const { data: conv } = useSWR<Conversation>(
    convId ? `/api/outreach/conversations/${convId}` : null,
    fetcher,
    { refreshInterval: 1500 },
  );

  async function startOutreach(customer_id: string) {
    setBusy(customer_id);
    setErr(null);
    try {
      const res = await fetch("/api/outreach/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_id, channel }),
      });
      const data = await res.json();
      if (res.status === 409 && data.reason === "ACTIVE_PTP") {
        setErr(`Suppressed — active promise-to-pay until ${data.promise_date}. No reminders are sent before the promise date passes.`);
      } else if (!res.ok) setErr(data.error ?? `Error ${res.status}`);
      else {
        setConvId(data.conversation_id);
        if (data.send_error) setErr(`Send recorded but delivery failed: ${data.send_error}`);
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
      refreshWb();
    }
  }

  async function submitPtp(row: Row) {
    if (!ptpForm) return;
    setBusy(row.customer_id);
    setErr(null);
    try {
      const editing = row.ptp?.status === "ACTIVE";
      const url = editing ? `/api/outreach/ptps/${row.ptp!.id}` : "/api/outreach/ptps";
      const body: Record<string, unknown> = { promise_date: ptpForm.date };
      if (!editing) body.customer_id = row.customer_id;
      if (ptpForm.amount) body.amount = Number(ptpForm.amount);
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) setErr(data.error ?? `Error ${res.status}`);
      else setPtpForm(null);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
      refreshWb();
    }
  }

  async function settlePtp(row: Row, status: "KEPT" | "CANCELLED") {
    if (!row.ptp) return;
    setBusy(row.customer_id);
    setErr(null);
    try {
      const res = await fetch(`/api/outreach/ptps/${row.ptp.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      const data = await res.json();
      if (!res.ok) setErr(data.error ?? `Error ${res.status}`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
      refreshWb();
    }
  }

  async function submitRekon(row: Row) {
    if (!rekonForm) return;
    setBusy(row.customer_id);
    setErr(null);
    try {
      const editing = row.restructure?.status === "ACTIVE";
      const url = editing ? `/api/outreach/restructures/${row.restructure!.id}` : "/api/outreach/restructures";
      const body: Record<string, unknown> = {};
      if (!editing) body.customer_id = row.customer_id;
      if (rekonForm.note) body.note = rekonForm.note;
      if (rekonForm.installment) body.new_installment = Number(rekonForm.installment);
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) setErr(data.error ?? `Error ${res.status}`);
      else setRekonForm(null);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
      refreshWb();
    }
  }

  async function settleRekon(row: Row, status: "ACCEPTED" | "DECLINED" | "CANCELLED") {
    if (!row.restructure) return;
    setBusy(row.customer_id);
    setErr(null);
    try {
      const res = await fetch(`/api/outreach/restructures/${row.restructure.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      const data = await res.json();
      if (!res.ok) setErr(data.error ?? `Error ${res.status}`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
      refreshWb();
    }
  }

  const rows = wb?.rows ?? [];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Collections & Recovery workbench"
        subtitle="Debtor collectibility (Kol-1..5), contact status and promise-to-pay tracking. The bot never chases a debtor whose promise-to-pay is still open."
      />

      <div className="flex flex-wrap items-center gap-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Channel</p>
        {["whatsapp", "sms", "email"].map((ch) => (
          <button
            key={ch}
            onClick={() => setChannel(ch)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
              channel === ch ? "bg-primary text-primary-foreground" : "bg-card hover:bg-muted"
            }`}
          >
            {ch}
          </button>
        ))}
        {busy && (
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Working…
          </p>
        )}
      </div>

      {err && (
        <p className="flex items-start gap-2 rounded-lg bg-red-50 p-2 text-xs text-red-800">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {err}
        </p>
      )}

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-3">Debtor</th>
              <th className="px-4 py-3">Collectibility</th>
              <th className="px-4 py-3">DPD · stage</th>
              <th className="px-4 py-3 text-center">Contacted</th>
              <th className="px-4 py-3 text-center">Replied</th>
              <th className="px-4 py-3">Last contact</th>
              <th className="px-4 py-3">Outcome</th>
              <th className="px-4 py-3">Promise to pay</th>
              <th className="px-4 py-3">Rekonstruksi</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-sm text-muted-foreground">
                  {wb ? "No demo debtors — is the collections bot reachable?" : "Loading workbench…"}
                </td>
              </tr>
            )}
            {rows.map((r) => {
              const active = r.ptp?.status === "ACTIVE";
              const formOpen = ptpForm?.cif === r.customer_id;
              const rekonActive = r.restructure?.status === "ACTIVE";
              const rekonOpen = rekonForm?.cif === r.customer_id;
              return (
                <tr key={r.customer_id} className="border-b last:border-0 align-top">
                  <td className="px-4 py-3">
                    <p className="font-medium">{r.name}</p>
                    <p className="text-xs text-muted-foreground">{r.customer_id}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${KOL_STYLE[r.collectibility] ?? "bg-muted"}`}
                      title={r.collectibility_source === "fallback" ? "Derived from DPD stage (no BigQuery row)" : "From mart_financing_health"}>
                      {r.collectibility_label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {r.current_dpd != null ? `DPD ${r.current_dpd}` : "—"}
                    <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium">{r.dpd_stage}</span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {r.contacted
                      ? <Check className="mx-auto h-4 w-4 text-emerald-600" />
                      : <Minus className="mx-auto h-4 w-4 text-muted-foreground" />}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {r.replied
                      ? <Check className="mx-auto h-4 w-4 text-emerald-600" />
                      : <Minus className="mx-auto h-4 w-4 text-muted-foreground" />}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {fmtWhen(r.last_contact_at)}
                    {r.last_channel && <span className="ml-1 capitalize">· {r.last_channel}</span>}
                  </td>
                  <td className="px-4 py-3">
                    {r.last_outcome
                      ? <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${OUTCOME_STYLE[r.last_outcome] ?? "bg-muted"}`}>{r.last_outcome}</span>
                      : <span className="text-xs text-muted-foreground">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    {r.ptp ? (
                      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${PTP_STYLE[r.ptp.status] ?? "bg-muted"}`}>
                        <CalendarClock className="h-3 w-3" />
                        {r.ptp.promise_date}
                        {r.ptp.amount != null && ` · RM ${r.ptp.amount.toLocaleString()}`}
                        {` · ${r.ptp.status}`}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                    {formOpen && (
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <input type="date" value={ptpForm.date}
                          onChange={(e) => setPtpForm({ ...ptpForm, date: e.target.value })}
                          className="rounded border bg-card px-2 py-1 text-xs" />
                        <input type="number" placeholder="RM amount" value={ptpForm.amount}
                          onChange={(e) => setPtpForm({ ...ptpForm, amount: e.target.value })}
                          className="w-24 rounded border bg-card px-2 py-1 text-xs" />
                        <button onClick={() => submitPtp(r)} disabled={!ptpForm.date || busy === r.customer_id}
                          className="rounded bg-primary px-2 py-1 text-xs font-medium text-primary-foreground disabled:opacity-40">
                          Save
                        </button>
                        <button onClick={() => setPtpForm(null)} className="rounded border px-2 py-1 text-xs">
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {r.restructure ? (
                      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${RESTRUCTURE_STYLE[r.restructure.status] ?? "bg-muted"}`}
                        title={r.restructure.note ?? undefined}>
                        <FileText className="h-3 w-3" />
                        {r.restructure.new_installment != null ? `RM ${r.restructure.new_installment.toLocaleString()}/mo` : "Offer"}
                        {` · ${r.restructure.status}`}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                    {rekonOpen && (
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <input type="text" placeholder="Plan note" value={rekonForm.note}
                          onChange={(e) => setRekonForm({ ...rekonForm, note: e.target.value })}
                          className="w-36 rounded border bg-card px-2 py-1 text-xs" />
                        <input type="number" placeholder="New RM/mo" value={rekonForm.installment}
                          onChange={(e) => setRekonForm({ ...rekonForm, installment: e.target.value })}
                          className="w-24 rounded border bg-card px-2 py-1 text-xs" />
                        <button onClick={() => submitRekon(r)} disabled={busy === r.customer_id}
                          className="rounded bg-primary px-2 py-1 text-xs font-medium text-primary-foreground disabled:opacity-40">
                          Save
                        </button>
                        <button onClick={() => setRekonForm(null)} className="rounded border px-2 py-1 text-xs">
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="ml-auto flex min-w-[11rem] flex-col gap-2">
                      {/* Primary action — the one dominant button */}
                      <button
                        disabled={busy === r.customer_id || r.suppressed || !r.channels.includes(channel)}
                        onClick={() => startOutreach(r.customer_id)}
                        title={active
                          ? `Suppressed until ${r.ptp?.promise_date} — active promise-to-pay`
                          : rekonActive
                            ? "Suppressed — active Rekonstruksi offer on the table"
                            : !r.channels.includes(channel) ? `No ${channel} destination` : `Send ${channel} reminder`}
                        className={`inline-flex w-full items-center justify-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed ${
                          r.suppressed || !r.channels.includes(channel)
                            ? "bg-muted text-muted-foreground"
                            : "bg-primary text-primary-foreground hover:bg-primary/90"
                        }`}
                      >
                        {r.suppressed ? <Lock className="h-3 w-3" /> : <Send className="h-3 w-3" />}
                        Send
                      </button>

                      <div className="border-t" />

                      {/* Promise-to-pay group */}
                      <div className="flex items-center gap-0.5">
                        <span className={GROUP_LABEL}>PTP</span>
                        <button
                          disabled={busy === r.customer_id}
                          onClick={() => setPtpForm(formOpen ? null : {
                            cif: r.customer_id,
                            date: active ? r.ptp!.promise_date : "",
                            amount: active && r.ptp!.amount != null ? String(r.ptp!.amount) : "",
                          })}
                          className={GBTN_NEUTRAL}
                        >
                          {active ? "Edit" : "Set"}
                        </button>
                        {active && (
                          <>
                            <button disabled={busy === r.customer_id} onClick={() => settlePtp(r, "KEPT")} className={GBTN_POSITIVE}>Kept</button>
                            <button disabled={busy === r.customer_id} onClick={() => settlePtp(r, "CANCELLED")} className={GBTN_MUTED}>Cancel</button>
                          </>
                        )}
                      </div>

                      {/* Rekonstruksi group */}
                      <div className="flex items-center gap-0.5">
                        <span className={GROUP_LABEL}>Rekon</span>
                        <button
                          disabled={busy === r.customer_id}
                          onClick={() => setRekonForm(rekonOpen ? null : {
                            cif: r.customer_id,
                            note: rekonActive ? r.restructure!.note ?? "" : "",
                            installment: rekonActive && r.restructure!.new_installment != null ? String(r.restructure!.new_installment) : "",
                          })}
                          className={GBTN_NEUTRAL}
                        >
                          {rekonActive ? "Edit" : "Set"}
                        </button>
                        {rekonActive && (
                          <>
                            <button disabled={busy === r.customer_id} onClick={() => settleRekon(r, "ACCEPTED")} className={GBTN_POSITIVE}>Accept</button>
                            <button disabled={busy === r.customer_id} onClick={() => settleRekon(r, "DECLINED")} className={GBTN_MUTED}>Decline</button>
                          </>
                        )}
                      </div>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>

      <Card className="flex min-h-[24rem] flex-col p-0">
        {!conv ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 py-12 text-center text-muted-foreground">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Radio className="h-6 w-6" />
            </div>
            <p className="text-sm">Send a reminder — the live conversation appears here.</p>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2 border-b p-4 text-xs">
              <span className="font-medium">{conv.customer_id}</span>
              <span className="rounded-full bg-muted px-2 py-0.5">DPD {conv.dpd} · {conv.stage}</span>
              <span className="rounded-full bg-muted px-2 py-0.5">Tone: {conv.tone}</span>
              <span className="rounded-full bg-muted px-2 py-0.5 uppercase">{conv.language}</span>
              {conv.detected_intent && (
                <span className="rounded-full bg-muted px-2 py-0.5">Intent: {conv.detected_intent}</span>
              )}
              <span className={`ml-auto rounded-full px-2 py-0.5 font-medium ${OUTCOME_STYLE[conv.outcome] ?? "bg-muted"}`}>
                {conv.outcome}
              </span>
            </div>
            <div className="flex-1 space-y-3 overflow-y-auto p-4">
              {conv.messages.map((m, i) => (
                <div key={`${m.ts}-${i}`} className={`flex ${m.direction === "out" ? "" : "justify-end"}`}>
                  <div
                    className={`max-w-[75%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
                      m.direction === "out"
                        ? m.status === "failed"
                          ? "border border-red-300 bg-red-50 text-red-900"
                          : "border bg-card"
                        : "bg-primary text-primary-foreground"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{m.body}</p>
                    <p className="mt-1 flex items-center gap-1 text-[10px] opacity-60">
                      <MessageSquare className="h-3 w-3" /> {m.channel} · {m.status}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </Card>

      <p className="text-xs text-muted-foreground">
        Collectibility is the regulatory 5-class view (demo OJK-style DPD bands); the bot&apos;s tone stages are a separate scale.
        A WhatsApp reply agreeing to pay is captured as a promise-to-pay automatically — sends stay locked until the promise date passes.
        A hardship reply opens a Rekonstruksi offer, which locks sends until an officer resolves it (Accept / Decline).
        Demo — AI-generated messages.
      </p>
    </div>
  );
}
