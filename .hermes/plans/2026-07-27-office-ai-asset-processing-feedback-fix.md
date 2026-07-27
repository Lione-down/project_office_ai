# Office AI Post-Alpha asset processing feedback fix

## Problem

Real browser uploads return `201`, but the workflow page renders only assets
whose processing and Evidence Manifest states are already `ready`. Pending and
rejected assets are hidden, and the page performs no processing refresh after
the immediate post-upload reload.

The current user's four uploaded workbooks are persisted and were correctly
rejected with `excel_sheet_limit_exceeded`; hiding that state makes the upload
look lost and gives no actionable recovery path.

The same investigation found a state-contract mismatch: the Worker and T2-002
evidence tests persist successful assets as `processing_status=ready` plus
`manifest_status=valid`, while the workflow, Brief input loader, and Preflight
still require the obsolete `ready/ready` combination. Without aligning those
consumers, a workbook inside the security limits would finish processing but
still remain unusable.

## Scope

- Show every active asset for the selected project on the workflow page.
- Align workflow, Brief, and Preflight readiness with the authoritative Worker
  state combination `processing_status=ready` and `manifest_status=valid`.
- Keep only that `ready/valid` combination selectable for generation.
- Show safe, actionable processing feedback for pending and rejected assets.
- Poll only while at least one asset is still processing; stop on terminal
  states and when the view unmounts.
- Automatically select the first ready asset through the existing defaults
  flow after a processing refresh.
- Preserve the 30-Sheet security limit, owner scope, upload API, database
  records, and existing user files.

## RED contract

1. A rejected XLSX remains visible by filename and explains that more than 30
   worksheets must be reduced before re-upload.
2. A quarantined asset is visible as processing, triggers a bounded refresh,
   and becomes selectable when the API later reports `ready/valid`.
3. Rejected assets never become selectable and never enable Brief submission.
4. Brief and Preflight accept the Worker's `ready/valid` state and continue to
   reject every incomplete or invalid state.

## Success criteria

- RED tests fail for the current hidden/non-polling behavior, then pass after
  the minimal UI fix.
- Focused frontend/Brief/Preflight tests, broad backend/frontend tests, and the
  production frontend build pass.
- Docker frontend is rebuilt and the real Chrome page shows the four rejected
  assets and their safe reason rather than an empty list.
- Backend security limits and the four user-owned rejected asset records remain
  unchanged.
- Documentation, security checks, exact staging, one conventional commit, and
  push complete without touching protected untracked paths.
