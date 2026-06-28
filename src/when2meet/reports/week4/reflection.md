## Learning points

- Customer-executed UAT surfaced incomplete room-booking logic: listing rooms is not enough without explicit time selection and intersection edge cases.
- Defining measurable quality requirements (ISO/IEC 25010) and linking them to automated QRTs made release confidence discussable in Sprint Review.
- CI gates (pytest, coverage, secret scanning) need to stay active after Assignment 4; they are product assets, not one-time coursework artifacts.
- A participant appearing in the list without selecting slots must not count as availability — a business rule easy to miss without live customer execution.

## Validated assumptions

- Short slug-based link sharing works end-to-end and was approved by the customer.
- SSO redirect and profile field transfer (email, Telegram) are production-viable for this increment.
- The team's earlier frontend design direction does not match customer expectations; usability feedback is now a first-class backlog driver.

## Friction and gaps

- UI/UX mismatch: slot self-selection and visual design need a dedicated redesign phase.
- Backend endpoint for editing participant replies is still missing outside the When2Meet service boundary.
- Reverse calendar overlay (UAT-001) was planned in the Sprint but not delivered.
- Room booking handles happy path only; zero/multiple intersection cases remain open.
- Deployment pipeline latency slowed iteration (see retrospective).

## Planned response

- **Quality and CI:** Keep Assignment 4 gates in [definition-of-done.md](../../docs/definition-of-done.md), [testing.md](../../docs/testing.md), and [quality-requirement-tests.md](../../docs/quality-requirement-tests.md); extend QRTs when new critical modules appear.
- **Customer feedback:** Track follow-up work in [#92](https://github.com/one-zero-eight/monorepo/issues/92)–[#100](https://github.com/one-zero-eight/monorepo/issues/100); prioritize accessibility and room-booking fixes in the next Sprint.
- **UAT:** Re-run [UAT-001](../../docs/user-acceptance-tests.md#uat-001--choose-a-meeting-time-with-calendar-event-awareness) and complete [UAT-003](../../docs/user-acceptance-tests.md#uat-003--book-an-available-room-for-a-selected-meeting-time) after room-booking and calendar overlay work ships.
- **Process:** Investigate deployment pipeline improvements (see [retrospective.md](retrospective.md)); schedule Sprint Review earlier so more team members can attend.
- **Roadmap:** Update [roadmap.md](../../docs/roadmap.md) after next Sprint Planning with linked PBIs for UI redesign, reverse calendar, and reply editing.
