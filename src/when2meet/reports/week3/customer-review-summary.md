# Customer Sprint Review Summary

**Date:** 20 June 2026

## Participants

| Role | Attendee |
| --- | --- |
| Customer | Customer |
| Product Owner / presenter | Nikita Lisitskiy |
| Scrum Master | Vladislav Konovalov |

Other team members were not present; frontend lead availability was noted during the meeting.

## Artifacts demonstrated

- Hosted MVP v1 frontend at [https://pre.innohassle.ru/when2meet](https://pre.innohassle.ru/when2meet) (staging preview used during preparation; demo walkthrough covered the meeting-creation and heatmap flows).
- Interactive UI: create meeting, share link dialog, manual participant slots, heatmap tooltips, participant search, “View all”.

## Scope reviewed

Planned MVP v1 scope from Sprint 1: **US-001**, **US-002**, **US-003**, **US-006** plus supporting implementation PBIs.

Implemented increment discussed:

- **US-001** — create meeting (name, description, shared time span across days).
- **US-003** — mark availability on the grid (“Available” / “If needed”), edit saved slots.
- **US-006** — heatmap with tooltips and participant search (partial; “Best time” UX rejected).
- **US-002** — share-link UI demonstrated; end-to-end link join not fully demonstrated live; supporting frontend PBI done, parent story [#56](https://github.com/one-zero-eight/monorepo/issues/56) remains open.

## Customer feedback and approval status

The customer **did not grant full acceptance** of the MVP v1 increment. Explicit change requests:

| Topic | Feedback | Backlog impact |
| --- | --- | --- |
| “Specific time” control | Wording and purpose unclear at meeting entry | UX copy/redesign; clarify per-day slot setup |
| Participant management | Manual add/remove not approved; expect InnoHassle SSO profiles | SSO integration prioritized for Sprint 2 |
| “Best time” / heatmap colors | Current purple gradient not usable at scale (~30 people) | Replace with filter showing maximum attendance intersection |
| Link sharing | Mechanics need clarification with frontend lead | Follow-up on share-link join flow |

## Risks

- Unauthorized participation without SSO enforcement.
- Heatmap accessibility when many participants overlap on similar shades.

## Action points

1. Clarify share-link join mechanics with the frontend developer.
2. Redesign “Specific time” entry for clarity.
3. Plan SSO-linked participant identity (validated in [reflection.md](reflection.md)).
4. Replace “Best time” gradient with a numeric intersection filter.

## Recording

Sprint Review recording is shared with instructors only (not committed to the repository): [Yandex Disk](https://disk.yandex.ru/d/NiTpSlSeKggsUg).

Sanitized English transcript: [customer-review-transcript.md](customer-review-transcript.md).
