### Testing

Follow the repository testing guidelines in [TESTING.md](TESTING.md).

! Assume that the test infrastructure is already running by developer (using `docker compose -f docker-compose.test.yaml up --wait`).

When writing tests:
- prefer behavior and contract tests over implementation-detail tests
- use shared test infrastructure
- mock only external systems
- keep tests independent and parallel-safe
- run the relevant pytest command before claiming the change is complete
