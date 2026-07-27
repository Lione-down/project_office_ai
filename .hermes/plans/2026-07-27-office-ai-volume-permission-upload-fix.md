# Office AI Post-Alpha volume permission upload fix

## Problem

The first real browser upload reaches `POST /api/v1/assets/uploads`, but the
backend returns `500`. Runtime evidence shows the non-root backend user
`10001:10001` cannot create `/app/files/users` because the fresh Compose named
volumes are mounted as `root:root` with mode `0755`.

The same ownership mismatch also affects the writable parsed, evidence, and
shared renderer volumes, so fixing only the upload directory would leave the
subsequent processing and rendering pipeline broken.

## Scope

- Add a one-shot, network-isolated Compose storage initializer.
- Initialize only the four application-owned named volume roots:
  `app-files`, `parsed-files`, `evidence-files`, and `shared-work`.
- Keep all long-running application services non-root.
- Make backend, worker, PPT renderer, and LibreOffice wait for successful
  initialization.
- Preserve MySQL data, the existing default project, user files, credentials,
  and protected untracked paths.
- Do not change upload API, database schema, or provider behavior.

## RED contract

The Compose contract must fail until it proves:

1. `storage-init` runs as root only for the one-shot ownership operation.
2. It has no network, a read-only root filesystem, no environment/Secret, and
   `no-new-privileges`.
3. It mounts exactly the four application data volumes and assigns their roots
   to `10001:10001` with mode `0750`.
4. Every long-running writer waits for `service_completed_successfully`.

## Success criteria

- Focused Compose contract changes from RED to GREEN.
- `docker compose config --quiet` succeeds.
- A temporary fresh named volume becomes writable by UID/GID `10001:10001`
  after the initializer contract runs, then is removed.
- Existing project volumes are initialized without deleting data.
- The real Docker stack is healthy and the browser upload request succeeds.
- The runtime fixture contains only synthetic text, is deleted through the
  product asset service after verification, leaves no active asset or physical
  file residue, and retains only the expected soft-deleted tombstone.
- Focused, broad, build, security, Git, and documentation checks pass before
  one conventional commit is pushed.
