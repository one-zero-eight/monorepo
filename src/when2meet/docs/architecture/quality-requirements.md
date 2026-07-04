# Architecture and Quality Requirements

This artifact maps each When2Meet quality requirement to the architectural
structures and decisions that support it. It is the architecture-side
companion to [../quality-requirements.md](../quality-requirements.md) (the
authoritative QR definitions and scenarios) and
[../quality-requirement-tests.md](../quality-requirement-tests.md) (the
automated QRTs). Together they form the traceability chain required by
Assignment 5: **quality requirement → architecture view(s) → ADR(s) →
quality requirement test**.

Quality requirements use the [ISO/IEC 25010](https://www.iso.org/standard/35733.html)
sub-characteristics. The table below is the index; each section that follows
explains how the current architecture supports that QR, which view(s) show the
supporting structure, and which ADR(s) captured the load-bearing decision.

## Contents

- [Traceability Index](#traceability-index)
- [QR-001: Critical module testability](#qr-001-critical-module-testability)
- [QR-002: Owner-only event mutation](#qr-002-owner-only-event-mutation)
- [QR-003: Event read response time](#qr-003-event-read-response-time)
- [QR-004: QA evidence traceability](#qr-004-qa-evidence-traceability)
- [Maintaining this mapping](#maintaining-this-mapping)

## Traceability Index

| QR | Sub-characteristic | Supporting views | ADRs | QRT |
|---|---|---|---|---|
| [QR-001](#qr-001-critical-module-testability) | Testability | Static, Dynamic | [ADR-0001](adr/0001-repository-pattern-for-events-persistence.md) | [QRT-001](../quality-requirement-tests.md#qrt-001-critical-module-line-coverage) |
| [QR-002](#qr-002-owner-only-event-mutation) | Confidentiality | Static, Dynamic, Deployment | [ADR-0001](adr/0001-repository-pattern-for-events-persistence.md), [ADR-0003](adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md) | [QRT-002](../quality-requirement-tests.md#qrt-002-owner-only-event-mutation) |
| [QR-003](#qr-003-event-read-response-time) | Time behaviour | Static, Dynamic, Deployment | [ADR-0002](adr/0002-slug-based-public-event-references.md) | [QRT-003](../quality-requirement-tests.md#qrt-003-event-read-response-time) |
| [QR-004](#qr-004-qa-evidence-traceability) | Maintainability | Static, Dynamic, Deployment | [ADR-0001](adr/0001-repository-pattern-for-events-persistence.md), [ADR-0002](adr/0002-slug-based-public-event-references.md), [ADR-0003](adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md) | [QRT-004](../quality-requirement-tests.md#qrt-004-qa-documentation-and-architecture-traceability) |

## QR-001: Critical module testability

**Scenario:** when a developer changes a critical When2Meet events module
(`routes.py`, `events_repo.py`, `schemas.py`) under the standard CI
environment, each critical module shall have automated tests that achieve at
least 30% line coverage.

**How the architecture supports it.** The static view draws an explicit
repository boundary between `Events Routes` and `Mongo Document Models`:
routes depend on the `events_repo` interface and never import Beanie or
pymongo directly. This separation lets each layer be tested with a different
double — routes with a mocked repository, the repository against the test
Mongo from `docker-compose.test.yaml`, and schemas purely — which is exactly
how the ≥30% coverage gate is met and exceeded (current coverage is 95% /
98% / 99% for the three critical modules).

**Supporting views:** [Static](README.md#static-view--component-diagram)
(the repository boundary), [Dynamic](README.md#dynamic-view--sequence-diagram)
(each step is individually testable).

**Decision of record:** [ADR-0001](adr/0001-repository-pattern-for-events-persistence.md).

**Verification:** [QRT-001](../quality-requirement-tests.md#qrt-001-critical-module-line-coverage).

## QR-002: Owner-only event mutation

**Scenario:** when an authenticated user who is not the event owner attempts
to update or delete that event under normal API operation, the When2Meet API
shall reject the request with HTTP 403 and shall not change stored event data.

**How the architecture supports it.** Two architectural choices combine to
enforce this:

1. Identity is resolved once per request by the `INH_TOKEN_AUTH` dependency
   against the InNoHassle Accounts JWKS (cached at startup), producing a
   trusted `auth.innohassle_id`. The static view shows this as the
   `Auth Dependency` component; the dynamic view shows it as the
   `resolve token → verify JWT against JWKS` exchange.
2. Owner-only and self-or-owner authorization checks live in `routes.py`
   immediately before any repository call, so there is a single choke point
   that cannot be bypassed by a code path that writes directly to Mongo. The
   repository boundary from ADR-0001 is what makes that choke point possible.

The deployment view reinforces this by keeping MongoDB off the public
internet — the only path to mutate event data is through the API container,
which always runs the authorization checks.

**Supporting views:** [Static](README.md#static-view--component-diagram)
(`Auth Dependency`, `Events Routes`), [Dynamic](README.md#dynamic-view--sequence-diagram)
(JWT verification step), [Deployment](README.md#deployment-view--deployment-diagram)
(Mongo not exposed publicly).

**Decisions of record:** [ADR-0001](adr/0001-repository-pattern-for-events-persistence.md),
[ADR-0003](adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md).

**Verification:** [QRT-002](../quality-requirement-tests.md#qrt-002-owner-only-event-mutation).

## QR-003: Event read response time

**Scenario:** when an authenticated user requests event details by ID under
the CI test environment with mocked dependencies, the
`GET /api/v0/events/{id}` endpoint shall return HTTP 200 within 2 seconds.

**How the architecture supports it.** The read path for a shared link is a
single indexed `find_one` on either the `_id` index (ObjectId) or the unique
`slug` index. The static view shows `Events Repository → Mongo Document
Models → MongoDB` with no intermediate service on the read path; the dynamic
view shows the `read_by_ref(slug) → find_one(slug) → Event document` exchange
as one repository call. The deployment view keeps MongoDB in the same Docker
Compose stack as the API, so the read is a local network round-trip with no
public-internet hop. JWKS caching (ADR-0003) ensures JWT verification on the
read path is local signature validation only, so authentication does not
threaten the 2 s budget.

**Supporting views:** [Static](README.md#static-view--component-diagram)
(indexed repository read), [Dynamic](README.md#dynamic-view--sequence-diagram)
(single-query read path), [Deployment](README.md#deployment-view--deployment-diagram)
(co-located API and Mongo).

**Decision of record:** [ADR-0002](adr/0002-slug-based-public-event-references.md)
(lookup path); [ADR-0003](adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md)
(JWKS caching keeps auth local).

**Verification:** [QRT-003](../quality-requirement-tests.md#qrt-003-event-read-response-time).

## QR-004: QA evidence traceability

**Scenario:** when Sprint 5 or later changes testing, QA, Definition of Done,
CI, or architecture evidence, maintained documentation shall remain navigable
and shall preserve traceability between required gates, quality requirements,
automated QRTs, and accepted ADRs.

**How the architecture supports it.** The product architecture is documented
as a single-service FastAPI API with explicit static, dynamic, deployment, and
ADR evidence. `QR-004` treats that documentation set as a maintained
architecture asset: if repository boundaries, slug lookup, JWT verification,
deployment, workflow, or CI gates change, the QR/QRT/ADR links must change in
the same increment.

**Supporting views:** [Static](README.md#static-view--component-diagram),
[Dynamic](README.md#dynamic-view--sequence-diagram),
[Deployment](README.md#deployment-view--deployment-diagram).

**Decisions of record:** [ADR-0001](adr/0001-repository-pattern-for-events-persistence.md),
[ADR-0002](adr/0002-slug-based-public-event-references.md),
[ADR-0003](adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md).

**Verification:** [QRT-004](../quality-requirement-tests.md#qrt-004-qa-documentation-and-architecture-traceability).

## Maintaining this mapping

This file is a maintained project asset. When a quality requirement is added,
changed, or retired, or when an ADR is accepted, deprecated, or superseded,
update the index table and the relevant section so the
QR → view → ADR → QRT traceability chain stays complete. The authoritative QR
definitions remain in [../quality-requirements.md](../quality-requirements.md);
this document only describes the architecture-side support and links.
