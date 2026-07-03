# ADR-0003: InNoHassle Accounts JWT verification and best-effort user enrichment

- **Status:** Accepted
- **Date:** 2026-06-29 (formalized for MVP v2 / Sprint 3)
- **Addresses:** [QR-002 Owner-only event mutation](../../quality-requirements.md#qr-002-owner-only-event-mutation)

## Context

When2Meet is one of several InNoHassle services that share a single identity
provider: the InNoHassle Accounts API, which issues JWTs, publishes their
public keys as a JWKS, and exposes user profile data (Innopolis email, name,
Telegram handle). The product needs two things from Accounts on almost every
request:

1. **Authentication** — confirm the caller is a real InNoHassle user and give
   the API a stable `innohassle_id`. This `innohassle_id` is the value used for
   ownership checks (`event.owner_id`) and participant identity
   (`participant.user_id`).
2. **Profile enrichment** — render participants with a readable name, email,
   and Telegram handle in `EventView`.

Assignment 4 quality requirement **QR-002** depends entirely on (1): if the
caller's identity can be spoofed or misresolved, the owner-only and
self-or-owner authorization checks in the routes layer are meaningless.

## Decision

Resolve identity through a single FastAPI dependency, `INH_TOKEN_AUTH`, that
verifies the caller's Bearer JWT against the InNoHassle Accounts JWKS and
returns the authenticated `innohassle_id`. The JWKS is fetched once and cached
at application startup in the `lifespan` handler via
`inh_accounts.update_key_set()`, so per-request verification is local signature
validation only.

Profile enrichment is handled separately and is **best-effort**: when building
an `EventView`, the routes layer calls `inh_accounts.get_users(participant_ids)`
to populate `ParticipantView` profile fields. If that call fails
(`httpx.HTTPError`, `ValidationError`, `ValueError`), the failure is logged
with a warning and the participants are still returned with `user_id` and
`availability` intact and profile fields set to `null`. Enrichment failure
never produces a 500 and never blocks availability submission.

## Alternatives considered

- **Verify JWTs in a dedicated middleware instead of a dependency.** Rejected:
  FastAPI dependencies give route-level type-safety and make the
  `innohassle_id` an explicit parameter, which keeps authorization checks
  readable and testable. Middleware would require manual request-state
  extraction.
- **Fetch the JWKS on every request.** Rejected: adds a network round-trip to
  Accounts on every call, which would blow the QR-003 2 s budget and create a
  hard dependency on Accounts availability for every read. Caching the JWKS at
  startup keeps verification local.
- **Block the response when enrichment fails.** Rejected: availability
  collection is the core product flow. A transient Accounts profile outage must
  not stop participants from submitting slots, and `user_id` + `availability`
  are enough for the heatmap. Best-effort enrichment is the right default.
- **Replicate Accounts profile data into the When2Meet Mongo.** Rejected:
  creates stale-profile and GDPR-consent problems and duplicates Accounts'
  source of truth. Reading profiles live (with graceful degradation) is
  simpler and always current.

## Consequences

- **Positive:** Identity is resolved in exactly one place (`INH_TOKEN_AUTH`),
  so the owner-only and self-or-owner checks in `routes.py` can rely on
  `auth.innohassle_id` for QR-002. Covered by
  [QRT-002](../../quality-requirement-tests.md#qrt-002-owner-only-event-mutation).
- **Positive:** JWKS caching keeps JWT verification local and fast, so it does
  not threaten QR-003.
- **Positive:** Best-effort enrichment means a Accounts profile outage degrades
  the UI (missing names) without breaking availability submission or reads.
- **Negative:** A JWKS rotation by Accounts requires a service restart to pick
  up new keys. The team accepts this because InNoHassle JWKS rotations are
  infrequent and the deploy pipeline makes restarts cheap.
- **Negative:** Enrichment is a per-response outbound call to Accounts. For
  events with many participants this is one batched `get_users` call, which is
  acceptable; if participant counts grow large, a short-lived profile cache
  should be introduced (tracked as future work).

## Traceability

- Quality requirement: [QR-002](../../quality-requirements.md#qr-002-owner-only-event-mutation)
- Quality requirement test: [QRT-002](../../quality-requirement-tests.md#qrt-002-owner-only-event-mutation)
- Implementation: [app.py](../../../app.py) (`lifespan`,
  `inh_accounts.update_key_set()`), [modules/events/routes.py](../../../modules/events/routes.py)
  (`INH_TOKEN_AUTH`, `event_view`, `build_participant_view`)
- Architecture views: [Static view](../README.md#static-view--component-diagram)
  (`Auth Dependency`, `Accounts`), [Dynamic view](../README.md#dynamic-view--sequence-diagram)
  (SSO + JWT verification + `get_users` enrichment), [Deployment view](../README.md#deployment-view--deployment-diagram)
  (external Accounts API)
