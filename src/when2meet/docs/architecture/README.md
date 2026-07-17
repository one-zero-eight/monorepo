# When2Meet Architecture

This is the maintained architecture artifact for the When2Meet service. It
documents the system from three complementary views, records the architecture
decisions behind the current design, and links those decisions back to the
quality requirements they support.

The architecture is versioned together with the product: every diagram and ADR
lives in this repository and is reviewed through the normal pull-request
workflow described in [development-process.md](../development-process.md).

## Overview

When2Meet is an InNoHassle service that helps organizers find a meeting time by
collecting participant availability on a shared grid and showing the
intersection as a heatmap. The product is delivered as:

- a **React single-page application** hosted at
  `https://pre.innohassle.ru/when2meet`, and
- a **FastAPI service** hosted at
  `https://api.innohassle.ru/when2meet/v0` that persists events and
  participant availability in MongoDB and verifies identity through the
  InNoHassle Accounts API.

MVP v3 (Sprint 5 final delivery) keeps the single-service API shape and hardens
it with owner-only mutation guards, slug-based sharing, calendar overlay,
selected final meeting time, timezone-safe room-booking integration, and
participant-reply editing.

## Views

The three required architectural views are stored as diagrams-as-code so the
sources are reviewed and versioned with the product. Each view directory below
contains the editable PlantUML source plus the rendered SVG and PNG.

### Static view — component diagram

- Source: [static-view/component-diagram.puml](static-view/component-diagram.puml)
- Rendered: [static-view/component-diagram.svg](static-view/component-diagram.svg) · [PNG](static-view/component-diagram.png)

**What the diagram shows.** The main internal components of the When2Meet API
(`App & Lifespan`, `Events Routes`, `Events Repository`, `Schemas & Validators`,
`Mongo Document Models`, `Auth Dependency`), the React frontend, the external
systems the product interacts with (InNoHassle Accounts API, Room Booking API,
Calendar API, MongoDB), and the communication paths between them — REST/HTTPS
at the edge, Beanie ODM reads/writes to MongoDB, and JWT/JWKS verification plus
`get_users` enrichment against Accounts.

**Coupling and cohesion.** The API is a single deployable FastAPI service
organized by feature. The `events` module is highly cohesive: routes,
repository, schemas, and document models for the same domain live together.
Cross-cutting concerns are deliberately isolated:

- HTTP and authorization stay in `routes.py` and the `INH_TOKEN_AUTH`
  dependency.
- Persistence stays behind `events_repo.py` (the repository boundary).
- I/O normalization stays in `schemas.py`.
- MongoDB shape stays in `mongo.py` (Beanie document models).

Routes depend on the repository interface, not on the database driver, so the
HTTP layer never imports Beanie or pymongo directly. This keeps coupling low
and lets each layer be replaced or tested independently.

**Maintainability implications.** Because persistence is hidden behind the
repository, Sprint 3 changes such as participant-reply editing (#97), slot-grid
change policy (#98), and room-booking integration (#93) touched `routes.py` and
`events_repo.py` without rippling into schemas or the frontend contract. New
features that need a new external integration (calendar overlay #92, room
booking #93) are added as outbound calls from `routes.py` rather than as new
shared mutable state, which keeps the blast radius of future changes small.

**Quality requirements supported or constrained.**

- The repository boundary directly supports **[QR-001](../quality-requirements.md#qr-001-critical-module-testability)**:
  `routes.py`, `events_repo.py`, and `schemas.py` can be unit-tested with a
  mocked repository or Mongo, which is how the ≥30% coverage gate is met.
- Owner-only mutation checks live in `routes.py` and back
  **[QR-002](../quality-requirements.md#qr-002-owner-only-event-mutation)**; see
  [ADR-0001](adr/0001-repository-pattern-for-events-persistence.md) and
  [ADR-0003](adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md).
- The indexed slug/ObjectId lookup (see
  [ADR-0002](adr/0002-slug-based-public-event-references.md)) supports
  **[QR-003](../quality-requirements.md#qr-003-event-read-response-time)** by
  keeping the shared-link read path a single indexed query.

### Dynamic view — sequence diagram

- Source: [dynamic-view/sequence-diagram.puml](dynamic-view/sequence-diagram.puml)
- Rendered: [dynamic-view/sequence-diagram.svg](dynamic-view/sequence-diagram.svg) · [PNG](dynamic-view/sequence-diagram.png)

**Scenario represented.** A participant opens a shared event link and submits
their availability. This is the core availability-collection flow that the
entire product exists to support.

**Why this scenario is important.** It is on the critical path for every
participant and exercises every backend component in a single interaction:
SSO login against InNoHassle Accounts, JWT verification through
`INH_TOKEN_AUTH`, slug-based event lookup, Beanie read from MongoDB,
participant enrichment via `inh_accounts.get_users`, slot validation against
`event.slots`, the participant upsert in `events_repo`, and the enriched
`EventView` response that the frontend turns into a heatmap.

**What it helps the reader reason about.**

- The **integration boundary** with Accounts: identity is resolved once per
  request by the auth dependency, and profile enrichment is a separate
  best-effort call that degrades gracefully (missing profiles become `null`
  fields, not 500s). This boundary is the subject of
  [ADR-0003](adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md).
- The **persistence boundary**: the API never lets the frontend write slots
  that are not in `event.slots`, which is the invariant that makes reply
  editing (#97) and slot-grid changes (#98) safe.
- The **quality requirements** the flow touches: QR-002 (only the
  authenticated participant can write their own availability), QR-003 (the read
  path is one indexed query plus one enrichment call), and QR-001 (every step
  is covered by an integration test in `tests/when2meet/test_events.py`).

### Deployment view — deployment diagram

- Source: [deployment-view/deployment-diagram.puml](deployment-view/deployment-diagram.puml)
- Rendered: [deployment-view/deployment-diagram.svg](deployment-view/deployment-diagram.svg) · [PNG](deployment-view/deployment-diagram.png)

**What the diagram shows.** The customer-facing access path
(browser → public internet → InNoHassle nginx edge → frontend host and API
host), the FastAPI container and Room Booking container on the API host, the
shared Docker host running MongoDB and MinIO, the external InNoHassle Accounts
API, and the GitHub Actions CI that builds and deploys both the SPA and the API
image on merge to `main`.

**Why this model was chosen.** When2Meet is a small service with a single
domain (events) and modest load. A single FastAPI container behind the existing
InNoHassle edge proxy reuses platform TLS termination, routing, and the shared
MongoDB instance, which keeps operational cost and configuration surface area
low. The React SPA is served as static assets from the same edge, so there is no
separate frontend runtime to operate. This matches the InNoHassle platform
convention used by sibling services in the monorepo.

**How the deployment supports or constrains the product.**

- **Supports:** fast deploys (rebuild `api.Dockerfile`, redeploy one
  container), simple configuration (`settings.yaml` mounted read-only), and a
  clear customer access path that the Week 5 report and SemVer release can
  point to.
- **Constrains:** the API is a single process with a 1 GB memory limit, so
  CPU-bound work (e.g. large intersection recomputation) must stay O(participants
  × slots). Horizontal scaling would require moving session affinity and the
  Accounts JWKS cache out of process state — tracked as future work.

**What to consider when deploying or operating for the customer.**

- MongoDB and MinIO run in the same Docker Compose stack as the API and are
  **not** exposed to the public internet; only the API port is published
  through the edge proxy.
- `settings.yaml` carries the Mongo URI and Accounts configuration and is
  mounted read-only; it must never be committed. The `when2meet-qa.yaml`
  gitleaks job prevents secret leakage.
- The hosted API and frontend URLs must be linked from the SemVer release and
  the Week 5 public report so graders and the customer can reach the increment
  until grading is complete.

## Architecture decision records

ADRs are stored under [adr/](adr/) and indexed in [adr/README.md](adr/README.md).
Each ADR identifies the Assignment 4 or later quality requirement(s) it
addresses.

| ADR | Decision | Status | Addresses |
|---|---|---|---|
| [ADR-0001](adr/0001-repository-pattern-for-events-persistence.md) | Repository pattern for events persistence | Accepted | QR-001, QR-002 |
| [ADR-0002](adr/0002-slug-based-public-event-references.md) | Slug-based public event references with ObjectId fallback | Accepted | QR-003 |
| [ADR-0003](adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md) | InNoHassle Accounts JWT verification and best-effort user enrichment | Accepted | QR-002 |

## How the architecture and the decisions fit together

The three views describe one system from three angles, and the three ADRs
explain the load-bearing choices that hold those views together:

- **ADR-0001** defines the repository boundary that the static view draws
  between `Events Routes` and `Mongo Document Models`, and that the dynamic
  view relies on for testable, isolated persistence.
- **ADR-0002** defines the slug + ObjectId lookup that makes the shared-link
  read path in the dynamic view a single indexed query, supporting the
  response-time quality requirement.
- **ADR-0003** defines the Accounts integration that appears in all three
  views: as the `Auth Dependency` + outbound `get_users` calls in the static
  view, as the SSO + JWT verification + enrichment steps in the dynamic view,
  and as the external Accounts API cloud in the deployment view.

Together they keep the service small, testable, and operable while leaving room
for the Sprint 3 additions (calendar overlay, room booking, reply editing)
without changing the overall shape.

## Related artifacts

- [quality-requirements.md](../quality-requirements.md)
- [quality-requirement-tests.md](../quality-requirement-tests.md)
- [testing.md](../testing.md)
- [definition-of-done.md](../definition-of-done.md)
- [development-process.md](../development-process.md)
- [roadmap.md](../roadmap.md)
- [interface.md](../interface.md)
