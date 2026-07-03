# Quality Requirements

When2Meet quality requirements use [ISO/IEC 25010](https://www.iso.org/standard/35733.html) sub-characteristics. Each requirement has a stable ID, a measurable scenario, and linked automated quality requirement tests in [quality-requirement-tests.md](quality-requirement-tests.md).

## QR-001: Critical module testability

**ISO/IEC 25010 sub-characteristic:** Testability

**Scenario:** When a developer changes a critical When2Meet events module under the standard CI environment, each critical module (`routes.py`, `events_repo.py`, `schemas.py`) shall have automated tests that achieve at least 30% line coverage for that module.

**Why this matters:** Event creation, participant updates, and API contracts are core scheduling workflows. Defects in these modules block organizers and participants from agreeing on meeting times.

**Linked quality requirement tests:** [QRT-001](quality-requirement-tests.md#qrt-001-critical-module-line-coverage)

**Related ADRs:** [ADR-0001 Repository pattern for events persistence](architecture/adr/0001-repository-pattern-for-events-persistence.md)

## QR-002: Owner-only event mutation

**ISO/IEC 25010 sub-characteristic:** Confidentiality

**Scenario:** When an authenticated user who is not the event owner attempts to update or delete that event under normal API operation, the When2Meet API shall reject the request with HTTP 403 and shall not change stored event data.

**Why this matters:** Meeting metadata belongs to the organizer. Unauthorized mutation would let other users rename, reschedule, or delete meetings they do not own.

**Linked quality requirement tests:** [QRT-002](quality-requirement-tests.md#qrt-002-owner-only-event-mutation)

**Related ADRs:** [ADR-0001 Repository pattern for events persistence](architecture/adr/0001-repository-pattern-for-events-persistence.md), [ADR-0003 InNoHassle Accounts JWT verification and user enrichment](architecture/adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md)

## QR-003: Event read response time

**ISO/IEC 25010 sub-characteristic:** Time behaviour

**Scenario:** When an authenticated user requests event details by ID under the CI test environment with mocked dependencies, the `GET /api/v0/events/{id}` endpoint shall return HTTP 200 within 2 seconds.

**Why this matters:** Loading meeting details is on the critical path for every participant opening a shared link. Slow reads make the grid unusable during live scheduling sessions.

**Linked quality requirement tests:** [QRT-003](quality-requirement-tests.md#qrt-003-event-read-response-time)

**Related ADRs:** [ADR-0002 Slug-based public event references with ObjectId fallback](architecture/adr/0002-slug-based-public-event-references.md)
