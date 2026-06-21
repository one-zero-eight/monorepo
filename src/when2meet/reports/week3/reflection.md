## Learning points

- Migrating stable user-story IDs into GitHub issues preserved traceability with [docs/user-stories.md](../../docs/user-stories.md) as the registry and issues as the live source of execution state.
- Product Backlog refinement (splitting frontend/backend PBIs, adding US-012/US-013 after customer themes) made Sprint Planning estimable; story points on the InNoHassle project board exposed sprint load early.
- Sprint Planning via milestone **Sprint 1** plus `mvp-v1` labeling kept MVP scope inspectable separately from later Sprints.
- MVP v1 delivery required cross-repo work (monorepo API + website UI); linking PR [#309](https://github.com/one-zero-eight/website/pull/309) to multiple issues preserved acceptance-criteria evidence.
- Customer Sprint Review surfaced gaps between prototype assumptions (manual participants, gradient heatmap) and InnoHassle product rules (SSO identity).
- Workflow enforcement (issue-linked branches, reviewed merge commits, changelog checklist) is course-required even when the customer prefers not to version InnoHassle services internally.

## Validated assumptions

| Assumption | Outcome |
| --- | --- |
| Mobile-first meeting-creation flow matches customer needs | **Partially confirmed** — flow works; “Specific time” labeling needs revision |
| Shareable link is the primary distribution mechanism | **Confirmed** — UI present; join-via-link needs follow-up with frontend lead |
| Heatmap helps pick a consensus time | **Partially confirmed** — tooltips useful; gradient “Best time” **rejected**; filter requested |
| Participants must map to InnoHassle SSO profiles | **Confirmed** — manual add rejected; SSO is next priority |
| FastAPI + MongoDB backend supports MVP v1 data model | **Confirmed** — [#59](https://github.com/one-zero-eight/monorepo/issues/59)–[#61](https://github.com/one-zero-eight/monorepo/issues/61) merged |

## Friction and gaps

- **US-002** parent story [#56](https://github.com/one-zero-eight/monorepo/issues/56) still open although share-link UI ([#307](https://github.com/one-zero-eight/website/issues/307)) is done — story not closable until SSO-linked join is verified.
- Task assignment lagged until the last sprint days (see [retrospective.md](retrospective.md)).
- No SSO enforcement yet — security risk flagged by customer.
- SemVer GitHub Release for course MVP mapping still pending (customer preference: no product versioning in InnoHassle; course tag `when2meet-v1.0.0` planned for submission).
- US-008–US-010 not yet migrated to issues.

## Planned response

| Gap | Action | Artifacts |
| --- | --- | --- |
| SSO participation | Implement InnoHassle SSO-linked identity for organizers and participants | Sprint 2 milestone, backlog refinement |
| Heatmap “Best time” | Replace gradient with maximum-intersection filter | Follow-up PBI after US-006 refinement |
| US-002 closure | Verify end-to-end share-link join on staging | [#56](https://github.com/one-zero-eight/monorepo/issues/56), [website#307](https://github.com/one-zero-eight/website/issues/307) |
| Sprint 2 scope | Calendar context, room booking, participant management (US-004, US-007, US-012, US-013) | [docs/roadmap.md](../../docs/roadmap.md), [milestone/2](https://github.com/one-zero-eight/monorepo/milestone/2) |
| Course release evidence | Tag `when2meet-v1.0.0` on `main` with MVP v1 description | [CHANGELOG.md](../../CHANGELOG.md) |
