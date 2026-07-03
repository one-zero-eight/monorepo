# ADR-0002: Slug-based public event references with ObjectId fallback

- **Status:** Accepted
- **Date:** 2026-06-22 (introduced in Sprint 2, reaffirmed for MVP v2)
- **Addresses:** [QR-003 Event read response time](../../quality-requirements.md#qr-003-event-read-response-time)

## Context

Participants reach a meeting through a shared link. MVP v0 used the 24-character
MongoDB ObjectId as the public identifier, which produced long, unfriendly URLs
that customers disliked (Sprint 1 feedback). At the same time, the read path
for a shared link is the hottest endpoint in the product: every participant
opening a link calls `GET /events/{ref}`, and Assignment 4 quality requirement
**QR-003** requires that read to return within 2 s in CI.

We needed a public identifier that was short, URL-safe, unique, unguessable
enough to act as a weak access token, and still resolvable in a single indexed
query so QR-003 would hold even as the events collection grows.

## Decision

Generate a short, unique, URL-safe `slug` for every event using
`secrets.token_urlsafe(6)` and store it as a **unique indexed** field on the
`Event` document. The public API accepts either the slug or the ObjectId as
`event_ref`; `events_repo.read_by_ref` resolves the right one with a regex
check on the 24-hex ObjectId pattern and otherwise falls back to a slug
`find_one`. Both paths use an index: the default `_id` index for ObjectId
lookups and the explicit `IndexModel("slug", unique=True)` for slug lookups.

Share links use the slug exclusively. The ObjectId remains available for
administrative and internal references.

## Alternatives considered

- **Keep ObjectId as the only public identifier.** Rejected: long URLs,
  customer-disliked, and exposes the creation-order pattern of ObjectIds.
- **Sequential integer or sequential slug.** Rejected: guessable, which would
  let an unauthenticated user enumerate events. Random `token_urlsafe` slugs
  act as a weak capability and avoid enumeration.
- **Hashids encoding of the ObjectId.** Rejected: reversible, still lengthens
  the URL, and adds a dependency for no QR-003 benefit over a random slug +
  unique index.
- **Separate `short_link` service / table.** Rejected as over-engineering for
  a single-service MVP; an indexed field on the same document keeps the read
  to one query.

## Consequences

- **Positive:** Shared links are short and friendly
  (`/when2meet/{slug}`), addressing Sprint 1 customer feedback.
- **Positive:** Slug lookup is a single indexed `find_one`, so the read path
  stays well under the QR-003 2 s budget; covered by
  [QRT-003](../../quality-requirement-tests.md#qrt-003-event-read-response-time).
- **Positive:** Random slugs prevent trivial enumeration of events.
- **Negative:** Slug generation is a retry loop until uniqueness is found; with
  a 6-byte token and the expected event volume, collision probability is
  negligible, but the loop is unbounded in theory. Accepted for an MVP.
- **Negative:** Two lookup paths (ObjectId and slug) in `read_by_ref` add a
  small amount of branching. The team accepts this to keep ObjectId available
  for internal/admin use without a second endpoint.

## Traceability

- Quality requirement: [QR-003](../../quality-requirements.md#qr-003-event-read-response-time)
- Quality requirement test: [QRT-003](../../quality-requirement-tests.md#qrt-003-event-read-response-time)
- Implementation: [modules/events/events_repo.py](../../../modules/events/events_repo.py)
  (`generate_unique_slug`, `read_by_ref`), [mongo.py](../../../mongo.py)
  (`IndexModel("slug", unique=True)`)
- Architecture view: [Dynamic view](../README.md#dynamic-view--sequence-diagram)
  (slug read path), [Static view](../README.md#static-view--component-diagram)
