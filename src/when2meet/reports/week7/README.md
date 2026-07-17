# Week 7 Final Report

## Summary

Week 7 completed the When2Meet final course delivery as **MVP v3**. The final increment keeps the hosted pre-production product available, documents the actual handover level, preserves customer-critical UAT evidence, and keeps Assignment 4 / Assignment 5 quality gates active for Sprint 5 changes.

Public product entry points:

| Resource | Link |
|---|---|
| Product | [pre.innohassle.ru/when2meet](https://pre.innohassle.ru/when2meet) |
| API / Swagger | [api.innohassle.ru/when2meet/v0/docs](https://api.innohassle.ru/when2meet/v0/docs) |
| Hosted docs | [one-zero-eight.github.io/monorepo](https://one-zero-eight.github.io/monorepo/) |
| Repository path | [src/when2meet](https://github.com/one-zero-eight/monorepo/tree/main/src/when2meet) |

## Final MVP v3 Outcome

The final course state is documented in the maintained [roadmap](../../docs/roadmap.md). Sprint 5 closes the roadmap with MVP v3 and does not add speculative post-course version planning.

Final course outcome:

- meeting creation, sharing, participant availability, and heatmap review remain available on the hosted product;
- calendar-aware availability selection remains documented and covered by UAT evidence;
- selected final meeting time is persisted and visible through the meeting API;
- room availability, booking, changing, synchronizing, canceling, and cleanup are tied to the meeting entity;
- selected meeting time for room booking must include an explicit timezone offset and is forwarded without backend timezone inference;
- customer handover, UAT, testing, quality requirements, QRTs, architecture, development process, and recovery guidance are maintained.

## Customer Handover

The actual handover state is documented in [customer-handover.md](../../docs/customer-handover.md).

Reached handover level:

- customer-facing product and API are available on Team 108 / InNoHassle hosted pre-production infrastructure;
- repository source, hosted docs, Swagger, testing guidance, UAT results, quality gates, and recovery guidance are available;
- runtime secrets, deployment host access, monitoring, rollback authority, and production ownership remain with Team 108 / InNoHassle maintainers unless separately transferred.

The documentation set is sufficient for independent use at the reached hosted pre-production level. Full customer-side operation would still require a separate transfer of deployment access, secret ownership, incident contacts, monitoring, and rollback responsibility.

## Week 7 UAT

Maintained scenarios and Week 7 results are recorded in [user-acceptance-tests.md](../../docs/user-acceptance-tests.md).

| Scenario | Week 7 result | Evidence |
|---|---|---|
| Calendar-aware availability selection | Passed by regression | Week 6 Sprint Review evidence; final docs review |
| Available-room lookup and booking for selected time | Passed | API contract tests and final selected-time timezone verification |
| Selected-slot distinction and heatmap legend | Passed with optional polish | Week 6 Sprint Review evidence; final docs review |
| Change, synchronize, and cancel booked room | Passed | API contract tests and final room-booking lifecycle verification |

No failed Week 7 UAT scenario is recorded in the public repository. Private recordings, exact private timecodes, consent evidence, customer-identifying details, and credentials are intentionally excluded.

## Quality And CI Evidence

Sprint 5 keeps Assignment 4 and Assignment 5 quality gates active:

- pytest and coverage for When2Meet critical modules;
- automated quality requirement tests QRT-001 through QRT-004;
- When2Meet secret scan through `.github/workflows/when2meet-qa.yaml`;
- link checking through `.github/workflows/lychee.yaml`;
- branch-protected `main` with required checks and review process.

Latest protected-default-branch evidence available at the time of this report:

| Check | Result | Link |
|---|---|---|
| Run tests | Success | [GitHub Actions run 29437789987](https://github.com/one-zero-eight/monorepo/actions/runs/29437789987) |
| When2Meet QA secret scan | Success | [GitHub Actions run 29437795124](https://github.com/one-zero-eight/monorepo/actions/runs/29437795124) |
| Links | Success | [GitHub Actions run 29437790384](https://github.com/one-zero-eight/monorepo/actions/runs/29437790384) |

Local verification command for the product scope:

```bash
uv run -m pytest tests/when2meet --cov=src/when2meet --cov-report=term-missing
```

## Related Maintained Artifacts

- [Roadmap](../../docs/roadmap.md)
- [Customer handover](../../docs/customer-handover.md)
- [User acceptance tests](../../docs/user-acceptance-tests.md)
- [Testing](../../docs/testing.md)
- [Quality requirements](../../docs/quality-requirements.md)
- [Quality requirement tests](../../docs/quality-requirement-tests.md)
- [Definition of Done](../../docs/definition-of-done.md)
- [Development process](../../docs/development-process.md)
- [Architecture](../../docs/architecture/README.md)
