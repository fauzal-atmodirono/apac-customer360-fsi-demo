# Collections & Recovery Workbench — Design

**Date:** 2026-07-06
**Status:** Implemented
**Builds on:** `2026-07-03-omnichannel-collections-bot-design.md`

## Problem

The collections bot can send DPD-toned reminders and adapt to replies, but the demo lacks
the operational view a collections team actually works from:

1. **Collectibility** — each debtor's regulatory 5-class classification (Kol-1..Kol-5).
2. **Contact status** — who has been contacted, who replied, over which channel, with what
   outcome.
3. **Promise-to-pay (PTP)** — when a debtor promises to pay, the bot must stop chasing
   them until the promise date passes; broken promises must resurface.

## Decisions

- **Collectibility lives in `mart_financing_health`** (Gold), derived from `current_dpd`
  with bands defined once in `dataform/includes/constants.js` (`COLLECTIBILITY`,
  `collectibilitySql`, `collectibilityLabelSql`). Demo assumption: OJK-style bands —
  Kol-1 = 0 DPD, Kol-2 = 1–90, Kol-3 = 91–120, Kol-4 = 121–180, Kol-5 = >180. The bot's
  tone stages (30/60/90) remain a deliberately separate scale.
- **PTP records live in the bot's store** (both SQLite and Firestore backends, identical
  method signatures): `{id, customer_id, conversation_id, promise_date, amount, status
  ACTIVE|KEPT|BROKEN|CANCELLED, source bot|manual, created_at, updated_at}`.
- **Capture is bot-first with manual override**: the reply-classification prompt also asks
  Gemini for `ptp_date`/`ptp_amount` on AGREE (tolerant parsing in `ptp.py`; no date →
  today + 3 days). Collectors can create/edit/settle PTPs from the dashboard.
- **Suppression is a guard on manual sends** (no scheduler): `POST /start` returns
  `409 ACTIVE_PTP` while an ACTIVE PTP is not past due. Past-due ACTIVE PTPs flip to
  BROKEN **lazily on read** (`active_ptp_for` / `mark_broken_ptps`), so sends resume the
  day after the promise date. Races between Cloud Run instances are idempotent.
- **Injectable clock**: `build_app(..., today_fn=clock.kl_today)` (Asia/Kuala_Lumpur);
  tests freeze it; `BOT_FAKE_TODAY` env overrides it for demos. Store PTP methods take
  `today` explicitly.
- **The webapp workbench merges two sources server-side** in `/api/workbench`:
  bot `/contacts` + `/outreach-summary` + `/ptps` (contact/reply/PTP state) with BigQuery
  `collectibilityForCifs` (Kol class). When BigQuery has no row for a demo contact, the
  class falls back from the contact's `dpd_stage` (SOFT/INTENSIVE/FIELD_VISIT → Kol-2,
  RECOVERY_LEGAL → Kol-3), mirroring the bot's own stage fallback.

## Components

- `dataform/includes/constants.js` + `definitions/gold/mart_financing_health.sqlx` —
  `collectibility` (1–5) and `collectibility_label` columns.
- `collections-bot/ptp.py` — pure PTP helpers; `clock.py` — KL date.
- `collections-bot/store.py` / `firestore_store.py` — PTP CRUD, `active_ptp_for`,
  `mark_broken_ptps`, `outreach_summary` (shared `_rollup`).
- `collections-bot/server.py` — `/start` 409 guard; AGREE → bot PTP (once per active);
  `GET|POST /ptps`, `POST /ptps/{id}`, `GET /outreach-summary`.
- `webapp/lib/bot.ts` (`botGet`), `lib/queries.ts` (`collectibilityForCifs`,
  `collectionsData().collectibility`), `app/api/workbench/route.ts` (merge).
- `webapp/app/(dashboard)/outreach/page.tsx` — the workbench: worklist table (Kol badge,
  contacted/replied, last contact, outcome, PTP chip, guarded Send + Set/Edit/Kept/Cancel
  PTP actions) above the live conversation panel.
- `webapp/app/(dashboard)/collections/page.tsx` — collectibility distribution chart + Kol
  column in the analytics worklist.

## Error handling

- BigQuery unreachable → workbench rows fall back to stage-derived Kol (flagged
  `collectibility_source: "fallback"`); the page keeps working for a bare local demo.
- LLM failure on inbound → degraded canned reply, no PTP recorded.
- Settled PTPs (KEPT/BROKEN/CANCELLED) are immutable (409); unknown ids 404; bad
  dates/CIFs 422.

## Testing

TDD throughout the bot (`collections-bot/tests/`, injected fakes, frozen `today_fn`, no
network): `test_ptp.py` (parsing/suppression edges), store twins (PTP CRUD, lazy break,
summary rollup), `test_conversation.py` (extraction), `test_server.py` (409 guard,
resume-after-date, AGREE→PTP once, endpoint auth/transitions). Webapp verified by
`tsc --noEmit` + `next build`; Dataform by `dataform compile`.

Demo script for suppression without waiting days: Edit PTP → set `promise_date` to
yesterday (past dates allowed by design) → next poll marks it BROKEN and Send unlocks;
or restart the bot with `BOT_FAKE_TODAY`.
