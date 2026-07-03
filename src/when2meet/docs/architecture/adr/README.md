# Architecture Decision Records

This directory contains the maintained Architecture Decision Records (ADRs) for
When2Meet. Each ADR records a single, significant architecture decision, its
context, alternatives considered, and consequences, and identifies the quality
requirement(s) it addresses.

## Index

| ID | Decision | Status | Addresses | Date |
|---|---|---|---|---|
| [ADR-0001](0001-repository-pattern-for-events-persistence.md) | Repository pattern for events persistence | Accepted | QR-001, QR-002 | 2026-06-15 |
| [ADR-0002](0002-slug-based-public-event-references.md) | Slug-based public event references with ObjectId fallback | Accepted | QR-003 | 2026-06-22 |
| [ADR-0003](0003-inh-accounts-jwt-verification-and-user-enrichment.md) | InNoHassle Accounts JWT verification and best-effort user enrichment | Accepted | QR-002 | 2026-06-29 |

## Status legend

- **Proposed** — drafted but not yet accepted by the team.
- **Accepted** — accepted and currently followed by the codebase.
- **Deprecated** — superseded by a later ADR; kept for history.
- **Superseded** — replaced by a specific later ADR (linked).

## Conventions

- File naming: `NNNN-kebab-case-title.md`, zero-padded sequential number.
- One decision per ADR.
- Each ADR links the Assignment 4 or later quality requirement(s) it addresses
  from [../quality-requirements.md](../quality-requirements.md).
- ADRs are never edited in place after acceptance except to mark them
  Deprecated or Superseded; new decisions get a new ADR.
- New ADRs are linked from [../README.md](../README.md) and from the relevant
  quality requirement in [../quality-requirements.md](../quality-requirements.md).
