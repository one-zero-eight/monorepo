# Definition of Done

Shared minimum completion standard for When2Meet PBIs in [one-zero-eight/monorepo](https://github.com/one-zero-eight/monorepo) and the [website](https://github.com/one-zero-eight/website) frontend.

A PBI may be marked **Done** only when all items below are satisfied.

## Issue and acceptance criteria

- All acceptance criteria in the issue are verified and recorded in the linked PR/MR.
- For user stories, all linked supporting PBIs required to satisfy the story acceptance criteria are **Done**.

## Review and merge

- Work is implemented on an issue-linked branch named `<issue-number>-short-description`.
- A focused PR/MR is opened, linked to the issue, and reviewed by a teammate other than the author.
- At least one approving review is recorded before merge.
- The PR/MR is merged into the protected default branch using a **merge commit** (no squash/rebase merge).

## Quality and verification

- Relevant automated checks pass (pre-commit, tests, Lychee where applicable).
- Manual verification is documented in the PR/MR (steps performed, environment, result).
- For user-visible changes, the delivered increment is reachable on the hosted preview or documented local setup.

## Documentation and traceability

- `docs/user-stories.md` work status and sprint assignment stay synchronized with the issue tracker.
- User-visible changes include an entry under `[Unreleased]` in [CHANGELOG.md](../CHANGELOG.md) (or the PR author marks the changelog checklist as not applicable).
- When a SemVer release maps to a course MVP milestone, included changelog entries move into the release section.

## Deployment

- Hosted frontend changes are deployable to `https://pre.innohassle.ru/when2meet` before the Sprint Review when the increment is customer-facing.
- API changes remain documented in [api/openapi.yaml](../api/openapi.yaml) and [docs/interface.md](interface.md).
