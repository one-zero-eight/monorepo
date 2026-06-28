## What went well

- Sprint 2 delivered a customer-accessible increment: event modes, slug-based sharing, SSO, deletion, calendar export, and initial room booking UI.
- Automated tests and CI covered critical event modules with high line coverage; Assignment 4 secret scanning added a distinct additional QA gate.
- Quality requirements and QRTs were defined with ISO/IEC 25010 sub-characteristics and linked to pytest evidence.
- Customer Sprint Review and customer-executed UAT happened in one recorded session with actionable feedback.
- Approved features (link sharing, SSO, deletion behaviour) reduce uncertainty about the technical foundation.

## What did not go well

- Frontend UX diverged from customer expectations; slot selection and visual design need substantial rework.
- Room booking and reverse calendar work were incomplete at UAT time despite being in Sprint scope.
- Sprint Review attendance was limited — not all developers joined the customer session.
- Long deployment times slowed verification and increased last-minute integration risk.
- Some backlog items were filed after submission drafting — now tracked as [#92](https://github.com/one-zero-eight/monorepo/issues/92)–[#100](https://github.com/one-zero-eight/monorepo/issues/100).

## What we changed compared to the previous Sprint retrospective

- Week 3 retrospective highlighted inconsistent task tracking and late assignments. Sprint 2 improved documentation of testing strategy (`docs/testing.md`) and maintained issue-linked PR workflow, but daily ownership visibility still needs discipline.
- Week 3 noted inconvenient meeting timing; we still scheduled Sprint Review without full team availability — this remains an improvement area.

## Process improvements for the next Sprint

1. **Assign and review every Sprint PBI on day one** with explicit internal deadlines and a short mid-Sprint progress check (carry-forward from Week 3, still not fully solved).
2. **Pick Sprint Review time using a team availability poll** so developers, QA, and the customer can attend; record UAT and review in one session when possible.
