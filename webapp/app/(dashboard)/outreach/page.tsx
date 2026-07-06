"use client";

import { useState } from "react";
import useSWR from "swr";
import { Radio, Loader2, MessageSquare, AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/insight";
import { Card } from "@/components/ui/card";

type Contact = { customer_id: string; name: string; dpd_stage: string; channels: string[] };
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

export default function OutreachPage() {
  const { data: contacts } = useSWR<Contact[]>("/api/outreach/contacts", fetcher);
  const [channel, setChannel] = useState("whatsapp");
  const [convId, setConvId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const { data: conv } = useSWR<Conversation>(
    convId ? `/api/outreach/conversations/${convId}` : null,
    fetcher,
    { refreshInterval: 1500 },
  );

  async function startOutreach(customer_id: string) {
    setSending(true);
    setErr(null);
    try {
      const res = await fetch("/api/outreach/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_id, channel }),
      });
      const data = await res.json();
      if (!res.ok) setErr(data.error ?? `Error ${res.status}`);
      else {
        setConvId(data.conversation_id);
        if (data.send_error) setErr(`Sent recorded but delivery failed: ${data.send_error}`);
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Collections outreach"
        subtitle="Bot-initiated omnichannel reminders (WhatsApp two-way, SMS + Email notice) with a DPD-driven tone that adapts to the debtor's reply."
      />

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card className="space-y-4 p-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Channel</p>
            <div className="flex gap-2">
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
            </div>
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Debtor (by DPD stage)</p>
            <div className="space-y-2">
              {(contacts ?? []).map((c) => (
                <button
                  key={c.customer_id}
                  disabled={sending || !c.channels.includes(channel)}
                  onClick={() => startOutreach(c.customer_id)}
                  className="flex w-full items-center justify-between rounded-lg border bg-card px-3 py-2 text-left text-sm transition-colors hover:bg-muted disabled:opacity-40"
                >
                  <span>
                    <span className="font-medium">{c.name}</span>
                    <span className="ml-2 text-xs text-muted-foreground">{c.customer_id}</span>
                  </span>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium">{c.dpd_stage}</span>
                </button>
              ))}
            </div>
          </div>
          {sending && (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Sending…
            </p>
          )}
          {err && (
            <p className="flex items-start gap-2 rounded-lg bg-red-50 p-2 text-xs text-red-800">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {err}
            </p>
          )}
        </Card>

        <Card className="flex min-h-[calc(100vh-16rem)] flex-col p-0">
          {!conv ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-muted-foreground">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Radio className="h-6 w-6" />
              </div>
              <p className="text-sm">Pick a debtor to start outreach — the live conversation appears here.</p>
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
      </div>
      <p className="text-xs text-muted-foreground">
        Bot-initiated · WhatsApp replies drive tone adaptation · SMS/Email are one-way notices. Demo — AI-generated messages.
      </p>
    </div>
  );
}
