# Demo Payment Overlay — design

**Date:** 2026-07-07 · **Status:** approved, ready to implement

## Problem

When a collections officer marks a promise-to-pay **KEPT** (the debtor paid), the
demo shows no financial effect — the arrears stay at the BigQuery figure (e.g.
RM 8,323) on both the dashboard and the bot's WhatsApp messages. Partial payments
are invisible, so the "they paid RM 1,000" story doesn't land.

BigQuery (core-banking Gold marts) is the real source of truth for balances and
must not be mutated by the bot. So we add a **demo overlay in Firestore** that
*subtracts* recorded payments from the displayed arrears, clearly labeled as a
demo stand-in for a real core-banking posting.

## The rule

```
paid_to_date(debtor) = Σ amount of that debtor's PTPs where status == KEPT
                       (a KEPT PTP with no amount contributes 0; multiple Kepts sum)
remaining_arrears     = max(0, arrears_from_bigquery − paid_to_date)
```

No new collection: the amount already lives on each KEPT PTP, so paid-to-date is
derived from existing data. This also makes multiple Kepts sum automatically.

## Consistency requirement (the load-bearing constraint)

The arrears figure is quoted in **two** surfaces, which must never disagree:

1. **Dashboard** — reads arrears from BigQuery (`collectibilityForCifs`).
2. **Bot WhatsApp messages** — reads arrears from BigQuery via `CaseLookup`.

Both subtract the **same** `paid_to_date` (same KEPT-PTP data, same rule), so they
stay consistent by construction.

## Scope

### Bot (Python)
- `store.paid_to_date(customer_id) -> float` (SQLite + Firestore): sum of KEPT PTP
  amounts. NULL amounts ignored.
- `server.py /start`: after `lookup.facts_for(...)`, set
  `facts.outstanding = max(0, facts.outstanding − paid_to_date)` before
  `compose_opening`. The dunning message then quotes the remaining balance.
  - Only the opening injects `outstanding`; reply turns use conversation history,
    so a fresh Send always reflects the current remaining. (Within an already-open
    thread, earlier messages keep their old figure — acceptable for the demo.)

### Dashboard
- `api/workbench/route.ts`: derive `paid_to_date` (Σ KEPT amounts) from the PTPs it
  already fetches; add `total_arrears` (original, BQ), `paid_to_date`,
  `remaining_arrears` to each row.
- `outreach/page.tsx` — **placement A**: under the Collectibility badge, when
  `paid_to_date > 0`, show a small muted line:
  `RM 7,323 left · RM 1,000 paid` (labeled as demo via tooltip/footnote).

### Not in scope
- DPD / Kol stay from BigQuery — a partial payment doesn't cure the arrears
  (Encik Tan stays Kol-3, DPD 120). Realistic and simpler.
- Auto-Kept via reconciliation — a possible follow-up, not this change.
- Writing back to BigQuery — never; BQ remains the untouched source of truth.

## Testing
- Bot, test-first: `store.paid_to_date` (SQLite + Firestore) — only KEPT counts,
  NULL amounts ignored, multiple Kepts sum; `/start` subtracts paid from the
  arrears quoted in the opening prompt.
- Webapp: `next build` clean; visual check on the deployed/local dashboard.
