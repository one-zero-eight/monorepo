# Customer Meeting Summary

**Date:** 2026-06-12

**Participants / roles:**

| Role | Participant |
| --- | --- |
| Customer | Customer representative (InnoHassle) |
| Prototype developer | Mikhail Istomin |
| Interviewer / team representative | Nikita Lisitskiy |
| Observers | Timur Khasanov, Vladislav Konovalov, Dmitrii Chudin |

**Recording and documentation:**

- Private instructor sharing: permitted (sanitized transcript in repository).
- Repository publication of transcript: permitted — published as [customer-meeting-transcript.md](customer-meeting-transcript.md).
- **MIT-licensed public development model:** Customer directed the team to develop When2Meet inside the existing public InnoHassle monorepo under the MIT license ([one-zero-eight/monorepo](https://github.com/one-zero-eight/monorepo), [LICENSE](https://github.com/one-zero-eight/monorepo/blob/main/LICENSE)). Development model accepted by continuing work in that repository.

**Artifacts demonstrated:**

- When2Meet mobile mockup — [Figma prototype](https://www.figma.com/design/Q31P4ba6YlmTOzoXC3W3E7/Untitled?node-id=0-1&t=8UaoXVNW08qHuwuY-1).
- Discussion of API conventions and InnoHassle design-system reuse (no live API demo in this meeting).

**Discussion points:**

- Integration targets: [Maps](https://github.com/one-zero-eight/monorepo/tree/main/src/maps), room booking, calendar (participant availability and exporting created events).
- Notifications: email only in InnoHassle today; push and Telegram not ready.
- API naming/versioning and design: align with [one-zero-eight](https://github.com/one-zero-eight) technical team; reuse InnoHassle UI components.
- Prototype walkthrough: open meetings list (removed), meeting creation (name, password removed, time slots), participant responses view.
- Missing prototype screens: meeting place creation/selection, response search, full page inventory.

**Decisions:**

| Topic | Decision |
| --- | --- |
| Integrations | Plan Maps, calendar, and room-booking integration for later phases (US-004, US-007). |
| Notifications | Not required now — aligns with US-008/US-009 as Could Have only. |
| API and design | Follow monorepo conventions; reuse InnoHassle components. |
| Open meetings | Remove from product — not a public events platform. |
| Meeting password | Remove — InnoHassle identity is sufficient; host removes unwanted participants. |
| Organizer flow | Keep calendar day selection, per-day time slots, and aggregated responses / heat map (US-001, US-006). |
| Link leakage | Mitigate by host reviewing participants, not passwords. |

**Customer approvals:**

| Item | Status |
| --- | --- |
| Documented user stories in [user-stories.md](user-stories.md) | Approved with updates after meeting (open meetings and password concepts dropped from prototype) |
| MoSCoW priorities | Approved for course scope; notifications and MEOW button remain low priority |
| Initial proposed MVP v1 scope (US-001, US-002, US-003, US-006) | Approved |
| Organizer time-selection flow and responses view | Approved |
| Removal of open meetings and password from prototype | Approved |
| Prototype / API artifacts | Feedback provided; formal approval not required |

**Action points:**

- Contact [one-zero-eight](https://github.com/one-zero-eight) technical team about API conventions.
- Remove open-meetings page and password field from Figma.
- Add prototype screens: meeting place, response search, participant management.
- Deploy frontend prototype — done at [https://pre.innohassle.ru/when-to-meet](https://pre.innohassle.ru/when-to-meet).

**Risks:**

- Incomplete prototype (missing place selection and search screens).
- No notification channel in InnoHassle for US-008/US-009.
- Calendar and room-booking integrations depend on external services.

**Feedback:**

- Customer expects full page inventory and sketches before polished UI.
- Response search explicitly missing from current Figma screens.

**Resulting changes:**

| Artifact | Change |
| --- | --- |
| [user-stories.md](user-stories.md) | Stable IDs US-001–US-010; MVP v1 scope US-001, US-002, US-003, US-006 |
| [Figma prototype](https://www.figma.com/design/Q31P4ba6YlmTOzoXC3W3E7/Untitled?node-id=0-1&t=8UaoXVNW08qHuwuY-1) | Remove open meetings and password; add missing screens |
| [api/openapi.yaml](../../api/openapi.yaml) | Event CRUD foundation; no password fields |
| Hosted frontend | [pre.innohassle.ru/when-to-meet](https://pre.innohassle.ru/when-to-meet) |

**Transcript:** [customer-meeting-transcript.md](customer-meeting-transcript.md)
