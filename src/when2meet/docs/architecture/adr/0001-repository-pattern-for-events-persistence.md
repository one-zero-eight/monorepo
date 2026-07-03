# ADR-0001: Repository pattern for events persistence

- **Status:** Accepted
- **Date:** 2026-06-15 (introduced in Assignment 4 / Sprint 1, reaffirmed for MVP v2)
- **Addresses:** [QR-001 Critical module testability](../../quality-requirements.md#qr-001-critical-module-testability), [QR-002 Owner-only event mutation](../../quality-requirements.md#qr-002-owner-only-event-mutation)

## Context

The events domain is the core of When2Meet: creating events, sharing them,
collecting participant availability, and returning enriched views. The first
implementation risked mixing MongoDB driver calls (`Beanie`, `pymongo`) with
HTTP request handling and authorization in the same functions, which would
make the routes hard to unit-test (Mongo would have to be spun up for every
test) and would scatter authorization checks next to `find_one` / `save`
calls.

Two quality requirements from Assignment 4 depend on this layer being clean:

- **QR-001 (Testability):** `routes.py`, `events_repo.py`, and `schemas.py`
  must each maintain ≥30% automated line coverage under CI. That is only
  practical if the HTTP layer can be tested with a fake repository and the
  repository can be tested against a real or test Mongo without HTTP.
- **QR-002 (Confidentiality / owner-only mutation):** non-owners must not be
  able to patch or delete events. The check has to live in exactly one place,
  applied before any persistence call, so it cannot be bypassed by a future
  code path that writes directly to Mongo.

## Decision

Introduce a single `events_repo.py` repository module as the only component
allowed to touch the `Event` Beanie document. The routes layer:

1. resolves identity through the `INH_TOKEN_AUTH` dependency,
2. enforces owner-only and self-or-owner authorization **before** calling the
   repository,
3. calls `events_repo` functions (`create`, `read_by_ref`, `update_event`,
   `update_participant`, `delete_event`, `delete_participant`,
   `get_my_events`, `get_participating_events`), and
4. maps results to `EventView` / `EventSummary` schemas.

The repository owns slug generation, ObjectId/slug resolution, participant
upsert, and document save/delete. Schemas (`schemas.py`) own request/response
normalization and slot validation. `mongo.py` owns the Beanie document shape
and indexes.

## Alternatives considered

- **Routes call Beanie directly.** Rejected: every route test would need a
  live Mongo, violating the spirit of QR-001 and slowing CI. Authorization
  checks would be duplicated across handlers, weakening QR-002.
- **Generic service class wrapping every document.** Rejected as
  over-engineering for a single-domain service; one `events_repo` module is
  enough and matches the feature-based module layout.
- **Active-record style methods on the `Event` document.** Rejected because it
  couples persistence behavior to the data model and makes the document harder
  to serialize/validate independently.

## Consequences

- **Positive:** `routes.py` is tested with a mocked repository; `events_repo.py`
  is tested against the test Mongo from `docker-compose.test.yaml`; `schemas.py`
  is tested purely. This is exactly how the QR-001 ≥30% coverage gate is met
  (current coverage is 95% / 98% / 99% for the three critical modules).
- **Positive:** Owner-only and self-or-owner checks live in the routes layer
  immediately before the repo call, so QR-002 is enforced at a single choke
  point and covered by `QRT-002`.
- **Negative:** Adding a new persistence operation requires a new repository
  function rather than a one-line Beanie call in a route. The team accepts this
  cost in exchange for the testability and authorization guarantees.
- **Negative:** The repository is a thin wrapper, so some functions are near
  pass-through. This is intentional and keeps the boundary stable for the
  Sprint 3 changes (reply editing #97, slot-grid change policy #98).

## Traceability

- Quality requirements: [QR-001](../../quality-requirements.md#qr-001-critical-module-testability),
  [QR-002](../../quality-requirements.md#qr-002-owner-only-event-mutation)
- Quality requirement tests: [QRT-001](../../quality-requirement-tests.md#qrt-001-critical-module-line-coverage),
  [QRT-002](../../quality-requirement-tests.md#qrt-002-owner-only-event-mutation)
- Implementation: [modules/events/events_repo.py](../../../modules/events/events_repo.py),
  [modules/events/routes.py](../../../modules/events/routes.py)
- Architecture views: [Static view](../README.md#static-view--component-diagram),
  [Dynamic view](../README.md#dynamic-view--sequence-diagram)
