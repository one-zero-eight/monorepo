# Definition of Done

A Product Backlog Item may be moved to **Done** only when all applicable conditions below are satisfied.
A condition may be marked **N/A** only with a clear justification in the pull request.

## Contents

- [1. Acceptance criteria and product behaviour](#1-acceptance-criteria-and-product-behaviour)
- [2. Code quality and review](#2-code-quality-and-review)
- [3. Testing and CI](#3-testing-and-ci)
- [4. Documentation and release readiness](#4-documentation-and-release-readiness)
- [5. Sprint evidence](#5-sprint-evidence)
- [6. Sprint 5 architecture and QA evidence](#6-sprint-5-architecture-and-qa-evidence)

## 1. Acceptance criteria and product behaviour

- [ ] Every acceptance criterion in the linked GitHub issue has been verified.
- [ ] Verification evidence is recorded in the pull request, such as automated-test results, screenshots, a short test description, or a deployed-environment check.
- [ ] The implemented behaviour does not break existing meeting creation, participant availability, heatmap calculation, or meeting-detail flows.
- [ ] User-facing errors and empty states are handled where relevant.

## 2. Code quality and review

- [ ] Changes are implemented in a dedicated branch and linked to the relevant GitHub issue.
- [ ] Code is readable, follows repository conventions, and contains no unnecessary debug output, dead code, secrets, or private customer data.
- [ ] At least one different team member has reviewed the pull request.
- [ ] Review comments are resolved or explicitly documented before merge.
- [ ] The change is merged through the protected default branch workflow.

## 3. Testing and CI

- [ ] Relevant unit tests are added or updated for changed business logic, components, hooks, services, or utilities.
- [ ] Relevant integration tests cover the complete affected user flow where practical.
- [ ] All required CI checks pass, including build, linting, formatting, type checks, pytest, coverage, QRTs, and additional QA checks configured for the repository.
- [ ] Changes to a critical module preserve at least 30% automated line coverage for that module, unless an approved exception is documented.
- [ ] Relevant Quality Requirement Tests pass and remain linked from `docs/quality-requirement-tests.md`.
- [ ] The When2Meet secret scan remains passing for `src/when2meet` and `tests/when2meet`.
- [ ] Test and CI evidence is preserved in the pull request, GitHub Actions run, or maintained project documentation.

## 4. Documentation and release readiness

- [ ] `docs/testing.md` is updated when test coverage, critical modules, test commands, or testing strategy changes.
- [ ] User documentation, API documentation, run instructions, or deployment instructions are updated when affected.
- [ ] `CHANGELOG.md` is updated for user-visible behaviour changes.
- [ ] The increment is deployable and does not require undocumented manual steps or private credentials.
- [ ] No credentials, access tokens, private recordings, or identifying customer data are committed to the repository.

## 5. Sprint evidence

- [ ] The GitHub issue is linked to its implementation pull request.
- [ ] The issue status, assignee, reviewer, Story Points, and Sprint milestone are current.
- [ ] The completed work can be demonstrated in the Sprint Review or UAT environment when it is part of the selected Sprint increment.

## 6. Sprint 5 architecture and QA evidence

- [ ] Assignment 4 gates remain active: pytest, CI, coverage, QRTs, secret scan, maintained testing docs, and this Definition of Done.
- [ ] If Sprint 5 changes architecture, critical modules, deployment model, workflow, or CI configuration, update `docs/architecture`, `docs/testing.md`, `docs/quality-requirements.md`, `docs/quality-requirement-tests.md`, and this file as applicable.
- [ ] If Sprint 5 changes customer-facing documentation, UAT evidence, or handover status, update `reports/week7/README.md` and keep it linked from roadmap, customer handover, UAT, and the root README.
- [ ] Long maintained docs touched by the change remain directly readable and navigable, including tables of contents where appropriate.
- [ ] `QRT-004` passes when QA evidence, architecture traceability, or Definition of Done content changes.
