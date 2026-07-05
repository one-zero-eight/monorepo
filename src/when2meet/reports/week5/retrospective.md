## What went well

- Sprint 3 delivered MVP v2 customer-facing improvements (calendar overlay, participant management, heatmap room booking) plus the Assignment 5 architecture and process documentation package.
- Maintained PlantUML views, ADRs, development-process docs, and GitHub Pages hosting are now reviewable in normal PR workflow.
- Customer Sprint Review and UAT ran in one recorded session with a public transcript in the repository.
- React frontend corrections and diagram regeneration removed inaccurate Vue references from architecture evidence.
- `gh-pages` docs deploy succeeded after switching away from flaky `deploy-pages` Actions deployment.

## What did not go well

- Room booking and calendar synchronization remain partial at UAT time despite milestone closure pressure.
- Participant UX still shows email-only rows and lacks deletion confirmation.
- `actions/deploy-pages` failed repeatedly even with Pages enabled; time was lost before adopting the branch deploy workaround.
- SemVer release `v0.2.0` was not created before report finalization, leaving release screenshot evidence incomplete.
- Not all team members attended the live customer session.

## What we changed compared to the previous Sprint retrospective

- Week 4 noted missing architecture docs and incomplete room booking; Sprint 3 addressed both in scope, but review showed lifecycle integration is still shallow.
- Week 4 noted long deploy latency; docs now deploy through `gh-pages` on merge to `main`.

## Process improvements for the next Sprint

1. **Create the SemVer release and update report screenshots on the same day as Sprint Review.**
2. **Treat “approved with changes” UAT outcomes as open PBIs immediately**, not as implicit Done states.
3. **Keep a single team availability poll** for customer Review/UAT so developers, QA, and PO attend together.
