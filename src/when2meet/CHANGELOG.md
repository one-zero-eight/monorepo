# Changelog

All notable user-visible changes to When2Meet are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and MVP milestones follow [Semantic Versioning](https://semver.org/) for course traceability.

## [Unreleased]

## [1.0.0] - 2026-06-21

Course MVP milestone: **MVP v1** (SWP Assignment 3, Sprint 1).

### Added

- Meeting creation with name, optional description, shared day/time span, and per-day slot selection ([#55](https://github.com/one-zero-eight/monorepo/issues/55), [website#306](https://github.com/one-zero-eight/website/issues/306)).
- Shareable meeting link flow in the UI ([#307](https://github.com/one-zero-eight/website/issues/307)); parent story [#56](https://github.com/one-zero-eight/monorepo/issues/56) remains open pending SSO-linked participation.
- Participant availability submission via the time-selection grid ([#58](https://github.com/one-zero-eight/monorepo/issues/58), [website#308](https://github.com/one-zero-eight/website/issues/308)).
- Aggregated availability heatmap with participant search ([#57](https://github.com/one-zero-eight/monorepo/issues/57)).
- Frontend wired to the When2Meet API instead of mock data ([website#304](https://github.com/one-zero-eight/website/issues/304), [PR #309](https://github.com/one-zero-eight/website/pull/309)).
- Backend event persistence and participant availability APIs ([#59](https://github.com/one-zero-eight/monorepo/issues/59)–[#61](https://github.com/one-zero-eight/monorepo/issues/61)).

### Changed

- Time zone selection form behavior on meeting creation ([website#305](https://github.com/one-zero-eight/website/issues/305)).

### Known gaps (customer review 2026-06-20)

- SSO-linked participants not yet enforced; manual participant entry shown in the demo.
- “Specific time” entry wording needs UX revision.
- “Best time” heatmap coloring to be replaced with a maximum-intersection filter.

[1.0.0]: https://github.com/one-zero-eight/monorepo/releases/tag/when2meet-v1.0.0
