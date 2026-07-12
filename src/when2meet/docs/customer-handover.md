# Customer Handover

This page describes the current actual handover state of When2Meet as of Week 6 (Sprint 4 trial release). It is customer-facing and should be kept current when access, deployment, configuration, limitations, or ownership changes.

## Current Status

When2Meet is an InNoHassle meeting availability planner. Organizers create a meeting grid, share a link, participants mark available slots, and the product shows aggregated availability as a heatmap.

Current product increment: **Week 6 trial release (0.3.0)**, deployed on Team 108 pre-production and customer-reviewed after Sprint 4. Final course delivery remains MVP v3 in Week 7.

Public entry points:

| Item | Location |
|---|---|
| Product | [https://pre.innohassle.ru/when2meet](https://pre.innohassle.ru/when2meet) |
| API / Swagger | [https://api.innohassle.ru/when2meet/v0/docs](https://api.innohassle.ru/when2meet/v0/docs) |
| Repository path | [one-zero-eight/monorepo/src/when2meet](https://github.com/one-zero-eight/monorepo/tree/main/src/when2meet) |
| Hosted documentation | [https://one-zero-eight.github.io/monorepo/](https://one-zero-eight.github.io/monorepo/) |

## Handover Scope

Transferred or available to the customer:

- Public MIT-licensed repository source under `src/when2meet`.
- Customer-facing product URL on the InNoHassle pre-production host.
- Hosted API documentation and Swagger UI.
- Maintained docs for interface, testing, quality requirements, architecture, development process, UAT, and reports.
- Public sanitized evidence in repository reports and docs.

Delegated to existing InNoHassle platform services:

- User authentication and profile enrichment through InNoHassle Accounts.
- Calendar context used by the frontend flow.
- Room booking integration through the InNoHassle room-booking product flow.

Intentionally retained by the team or InNoHassle maintainers:

- GitHub repository administration, branch protection, release tags, and CI configuration.
- Production-like deployment ownership for `pre.innohassle.ru` and `api.innohassle.ru`.
- Runtime `settings.yaml`, MongoDB credentials, service tokens, server access, TLS, reverse proxy, and Docker host access.
- Private customer recordings, consent evidence, and any non-public credentials.

Customer confirmed that deployment on Team 108’s side is complete and the project has been transferred to Team 108 for hosted operation. No separate customer-owned infrastructure deployment has been completed.

## Customer Access And Use

Normal customer use:

1. Open [https://pre.innohassle.ru/when2meet](https://pre.innohassle.ru/when2meet).
2. Sign in with InNoHassle SSO.
3. Create a meeting with candidate dates or time slots.
4. Share the generated meeting link with participants.
5. Participants open the link, sign in, and submit availability.
6. Organizer reviews the heatmap, participant filters, and available-room flow.
7. Organizer chooses a final time and, where suitable, books a room.

API use:

- Use [Swagger UI](https://api.innohassle.ru/when2meet/v0/docs) for manual API checks.
- Send `Authorization: Bearer <JWT>` from InNoHassle Accounts for authenticated calls.
- See [interface.md](interface.md) for endpoints and request/response contracts.

## Configuration And Secrets

Runtime configuration is loaded from the repository-root `settings.yaml` through typed pydantic settings. The file is mounted read-only in Docker and must not be committed.

Required configuration areas:

| Area | Required setting or service | Notes |
|---|---|---|
| Accounts | `accounts.api_jwt_token`, `accounts.api_url` | Token is a secret. `accounts.mock` is development-only. |
| When2Meet service | `when2meet_service.environment`, `app_root_path`, `cors_allow_origin_regex` | Hosted API path is `/when2meet/v0`; local API path is `/api/v0`. |
| MongoDB | `when2meet_service.mongo.uri` | Secret connection string. Database defaults to the service name if the URI does not include a database. |
| Frontend | API base URL and SSO integration | Deployed static SPA is served from `pre.innohassle.ru/when2meet`. |
| External services | InNoHassle Accounts, MongoDB, Room Booking, Calendar context | Accounts and MongoDB are required for backend startup; room/calendar behavior has known limitations below. |

Secrets-handling expectations:

- Do not commit `settings.yaml`, real JWTs, MongoDB credentials, service tokens, private keys, recordings, timecodes, or consent evidence.
- Use placeholders from `settings.example.yaml` only as examples; replace them with real secrets through deployment configuration.
- Mount `settings.yaml` read-only in containers.
- Keep production secrets in the platform secret store or server-side deployment environment.
- Run the When2Meet secret scan before merge when documentation or config examples change.

## Local Setup

Use this only for development or verification, not for customer production operation.

1. Install `uv` and Docker.
2. Install dependencies:

   ```bash
   uv sync
   ```

3. Start shared infrastructure:

   ```bash
   docker compose up --wait mongodb minio
   ```

4. Create or update repository-root `settings.yaml` from `settings.example.yaml`. Configure `accounts.api_jwt_token` and `when2meet_service`.
5. Run the API:

   ```bash
   uv run -m src.when2meet --reload
   ```

6. Open local API docs at `http://localhost:8020/docs` or call the local API at `http://localhost:8020/api/v0`.

## Deployment

Current deployment model:

- React SPA is served from `pre.innohassle.ru/when2meet`.
- FastAPI backend is served from `api.innohassle.ru/when2meet/v0`.
- InNoHassle edge nginx handles TLS and path routing.
- The When2Meet API container is built from `api.Dockerfile` with `APP_MODULE=src.when2meet.app:app`.
- The service container maps `8020:8000` and mounts `./settings.yaml:/app/settings.yaml:ro`.
- MongoDB is internal to the Docker host and is not exposed to the public internet.

Release/deploy flow:

1. Merge reviewed feature work into `develop`.
2. Fast-forward or merge `develop` to protected `main` for the release.
3. Tag the SemVer release that maps to the MVP increment.
4. CI builds the API container and SPA.
5. Deployment updates the hosted API and frontend.
6. Verify the product and Swagger URLs.

More detail: [development-process.md](development-process.md) and [architecture deployment view](architecture/README.md).

## Recovery

If the hosted product is unavailable:

1. Check whether [https://pre.innohassle.ru/when2meet](https://pre.innohassle.ru/when2meet) loads.
2. Check whether [https://api.innohassle.ru/when2meet/v0/docs](https://api.innohassle.ru/when2meet/v0/docs) loads.
3. Check the latest GitHub Actions runs for tests, secret scan, link check, and docs deploy.
4. On the deployment host, verify the When2Meet container is running and has the read-only `settings.yaml` mount.
5. Verify MongoDB is reachable from the API container.
6. Verify InNoHassle Accounts JWKS/profile access if authentication or profile display fails.
7. Roll back to the previous release tag or redeploy the previous known-good container if a release caused the outage.

If event data is affected:

- Do not delete MongoDB data during recovery.
- Preserve current database state before manual repair.
- Confirm event ownership and participant data through API reads before applying fixes.

## Verification

Run product-scoped automated checks:

```bash
uv run -m pytest tests/when2meet --cov=src/when2meet --cov-report=term-missing
```

Run the additional secret scan:

```bash
docker run --rm -v "$PWD:/repo" ghcr.io/gitleaks/gitleaks:latest dir --no-banner --redact --verbose /repo/src/when2meet
docker run --rm -v "$PWD:/repo" ghcr.io/gitleaks/gitleaks:latest dir --no-banner --redact --verbose /repo/tests/when2meet
```

Manual smoke check:

1. Open the hosted product and sign in.
2. Create a meeting.
3. Open the shared link as a participant.
4. Submit availability.
5. Confirm the organizer sees the participant response and heatmap.
6. Open Swagger UI and confirm event endpoints are listed.

## Known Limitations And Risks

- The Week 6 trial release is deployed and customer-reviewed; final MVP v3 confirmation is Week 7 work.
- Heatmap legend is present but should move from the bottom to the top of the interface.
- Selected final meeting time cannot always be cleared; organizers may need a reset before MVP v3.
- Mobile layout still needs formal customer validation before final release.
- Hide-calendar-events toggle and some participant-management polish remain optional follow-ups.
- Reply editing through the wider platform API remains blocked outside the When2Meet service boundary.
- Stronger handover still requires customer-side operational access, runbook ownership, incident contacts, and secret rotation responsibility if those are desired later.

## Handover Status

Current level reached: **Ready for independent use**.

Customer-confirmation status for this document and the README entry point: **Accepted**.

The customer reviewed `README.md` and this handover page during the Week 6 meeting and stated that the documentation matches her expectations. The customer also confirmed that UAT scenarios from [user-acceptance-tests.md](user-acceptance-tests.md) behave as expected for the trial release.

This means the customer can access and use the deployed pre-production product with InNoHassle SSO, and the repository/docs are sufficient to understand current normal use, API behavior, setup, testing, deployment model, known gaps, and recovery expectations for the reached handover level.

Stronger levels not fully reached:

- **Independently used by customer:** trial use confirmed; routine independent use without team support is still being established.
- **Deployed or operated on customer side:** not reached because deployment, infrastructure, secrets, and repository administration remain with Team 108 / InNoHassle maintainers (customer confirmed transfer to Team 108 hosted operation, not customer-owned infra).

Remaining support needed:

- Team support for deployment operations, incident recovery, secret rotation, and CI/release management.
- Sprint 5 product follow-ups: legend placement, selected-time clear, mobile validation.
- Post-course availability for bug fixes and user-driven improvements, as requested by the customer.

The current documentation is sufficient for the reached handover level. It is not sufficient for full customer-side operation until deployment access, secret ownership, monitoring, rollback authority, and incident responsibilities are formally transferred.

## Related Documentation

- [Interface](interface.md)
- [User acceptance tests](user-acceptance-tests.md)
- [Testing](testing.md)
- [Quality requirements](quality-requirements.md)
- [Quality requirement tests](quality-requirement-tests.md)
- [Definition of Done](definition-of-done.md)
- [Development process](development-process.md)
- [Architecture](architecture/README.md)
- [Roadmap](roadmap.md)
- [Week 6 report](../reports/week6/README.md)
- [Week 5 report](../reports/week5/README.md)
- [CHANGELOG](../CHANGELOG.md)
