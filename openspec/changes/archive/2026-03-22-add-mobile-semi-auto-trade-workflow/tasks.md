## 1. Command Center Read Model (V1)
- [x] 1.1 Extend `/api/mobile/dashboard` with approval card fields: action type, target weight / suggested quantity, reason tags, exit tags, freshness, and blockers.
- [x] 1.2 Show system suggestion and user-confirmed state side by side for the same symbol in the mobile UI.
- [x] 1.3 Add pre-confirm blockers for stale data, duplicate submission, risk lock, and executor unavailable.

## 2. Approval And Pending Queue Protocol (V1)
- [x] 2.1 Add `outputs/mobile_ops/approval_tickets/`, idempotency mapping, and append-only `audit_log.jsonl`.
- [x] 2.2 Add mobile prepare/commit/reject/edit APIs with server-side second confirmation enforcement.
- [x] 2.3 Add pending ticket query and revoke APIs for `approved_pending` tickets.

## 3. Executor Coordination And Status Writeback (V2)
- [x] 3.1 Define how the desktop executor consumes approval tickets.
- [x] 3.2 Add `execution_events/` protocol and ticket lifecycle state machine.
- [x] 3.3 Add mobile execution status page and event stream view.
- [x] 3.4 Add timeout, reject, and partial-fill exception handling flow.

## 4. Private HTTPS And PWA (V3)
- [x] 4.1 Add manifest, service worker, install entry, and browser-mode / PWA-mode split.
- [x] 4.2 Extend private-host restrictions to manifest, service worker, and related static resources.
- [x] 4.3 Document private HTTPS deployment without exposing a public domain.

## 5. Notifications And Daily Briefing (V3)
- [x] 5.1 Generate structured pre-open todo and execution anomaly summary objects.
- [x] 5.2 Add post-close daily recap cards based on execution events.
- [x] 5.3 Integrate the first private notification channel and define downgrade behavior.

## 6. Verification And Docs
- [x] 6.1 Add fuller automation coverage for write-side flows, state transitions, PWA access limits, and structured summaries.
- [x] 6.2 Update README / ops docs / audit notes to explain mobile boundaries, desktop execution ownership, second confirmation, and rollback.
