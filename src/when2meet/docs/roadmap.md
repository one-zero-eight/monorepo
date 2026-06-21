# Roadmap

Sprint-by-sprint delivery plan for When2Meet. Full user-story registry: [user-stories.md](user-stories.md).

## Sprint 1 — MVP v1

**Milestone:** [Sprint 1](https://github.com/one-zero-eight/monorepo/milestone/1)  
**Dates:** 15 June 2026 — 21 June 2026 (due 20 June 2026)

**Sprint Goal:** Release a basic working version of the service (MVP v1) so organizers can create meetings and share an invitation link, and participants can mark free time on the grid and see an availability heatmap.

**Focus / expected outcome:** End-to-end meeting availability flow through a shareable link on staging.

**Planned items:**

- [#55](https://github.com/one-zero-eight/monorepo/issues/55) — US-001: Create a new meeting
- [#56](https://github.com/one-zero-eight/monorepo/issues/56) — US-002: Share a meeting link
- [#58](https://github.com/one-zero-eight/monorepo/issues/58) — US-003: Connect and submit time
- [#57](https://github.com/one-zero-eight/monorepo/issues/57) — US-006: View participant heatmap
- [#59](https://github.com/one-zero-eight/monorepo/issues/59) — Setup database schema and core models
- [#60](https://github.com/one-zero-eight/monorepo/issues/60) — Implement logic to create a meeting
- [#61](https://github.com/one-zero-eight/monorepo/issues/61) — Implement logic to save participant availability
- [website#304](https://github.com/one-zero-eight/website/issues/304) — Replace mock data with real API endpoints
- [website#305](https://github.com/one-zero-eight/website/issues/305) — Fix time zone selection form
- [website#306](https://github.com/one-zero-eight/website/issues/306) — Create a new meeting (US-001 UI)
- [website#307](https://github.com/one-zero-eight/website/issues/307) — Share meeting link component (US-002 UI)
- [website#308](https://github.com/one-zero-eight/website/issues/308) — Participant time selection grid (US-003 UI)

## Sprint 2 — Meeting management and calendar context

**Milestone:** [Sprint 2](https://github.com/one-zero-eight/monorepo/milestone/2)  
**Dates:** 22 June 2026 — 28 June 2026

**Sprint Goal:** Improve scheduling decisions with SSO-linked identity, calendar awareness, and organizer controls.

**Focus / expected outcome:** Participants are tied to InnoHassle profiles; organizers can manage participation; heatmap filter replaces rejected “Best time” gradient.

**Planned items:**

- [#66](https://github.com/one-zero-eight/monorepo/issues/66) — US-004: Calendar-event awareness while choosing times
- [#67](https://github.com/one-zero-eight/monorepo/issues/67) — US-007: Book a room for the selected time
- [#68](https://github.com/one-zero-eight/monorepo/issues/68) — US-012: Remove unnecessary participants
- [#69](https://github.com/one-zero-eight/monorepo/issues/69) — US-013: Find a participant and view their availability
- Close [#56](https://github.com/one-zero-eight/monorepo/issues/56) after SSO-linked share/join is verified
