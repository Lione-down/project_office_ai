# Office AI Post-Alpha Excel limit and rejected asset deletion

## Problem

The current parser rejects workbooks above 30 Sheets. The user explicitly
approves raising that default safety boundary to 100 Sheets. Rejected assets
are now visible, but repeated attempts accumulate with no row-level cleanup
action in the workflow.

## Scope

- Raise the default Excel input limit from 30 to 100 Sheets in Settings,
  ProcessingLimits, Worker Compose configuration, tests, and documentation.
- Keep 100 Sheets accepted and reject 101 with the existing stable
  `excel_sheet_limit_exceeded` error code.
- Preserve the independent 300,000 non-empty-cell, archive, structural,
  memory, timeout, ClamAV, owner-scope, and Evidence gates.
- Reuse the existing owner-scoped `DELETE /assets/{asset_id}` endpoint.
- Show a quiet right-aligned `×` action only for rejected or invalid assets.
- Confirm the exact filename before deletion, disable the row action while
  deleting, remove the row after HTTP 204, and keep it visible with an
  actionable error if deletion fails.
- Do not delete existing rejected assets automatically and do not read user
  file contents.

## RED contract

1. Default Settings, ProcessingLimits, and Worker Compose resolve the Sheet
   limit to 100.
2. Excel shape and parser accept exactly 100 Sheets and reject 101.
3. Workspace API exposes the existing authenticated asset DELETE contract.
4. A rejected row renders a filename-scoped delete button and the 100-Sheet
   recovery message; ready and processing rows do not render that action.
5. Cancelling confirmation performs no request.
6. Confirmed deletion calls the exact asset endpoint once and removes only
   that row after success.
7. A failed deletion leaves the row visible and shows the safe API error.

## Success criteria

- Every new contract is observed failing before production changes.
- Focused parser/settings/workspace/workflow tests pass, followed by complete
  Backend and Frontend suites and the production Frontend build.
- Worker and Frontend are rebuilt without recreating MySQL/Redis or deleting
  current user assets.
- Real Chrome at `http://localhost:8888` shows the four rejected rows with
  right-side delete controls, updated 100-Sheet guidance, and no console
  warning/error at desktop and 375px width.
- Documentation, security checks, exact staging, one conventional commit, and
  push complete without protected untracked paths or sensitive material.
