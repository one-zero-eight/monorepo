Be concise. Avoid overly long explanations. Provide direct answers, or apply code solutions with minimal extra commentary. Only include clarifications if explicitly requested or really necessary, to reduce token usage and keep responses focused. Don't ask for unecessary permission, just go.

### Code

DO NOT CREATE useless md files such as QUICKSTART, TASK and so on.
DO NOT MAKE ridiculous fallbacks.
DO NOT MAKE any backward compatibility shit unless requested.
DO NOT EVER WRITE "try: import ... except", as all libraries are expected to be installed.
DO NOT WRITE "from __future__ import annotations", as Python 3.14+ uses deferred annotations by default.
DO NOT USE response_model= in route decorator, use type hints instead:

    ```python
    # Good.
    @router.get("/scenes/")
    async def scenes() -> list[Scene]:
        return await repo.get_all_scenes()

    # Bad.
    @router.get("/scenes/", response_model=list[Scene])
    async def scenes():
        return await repo.get_all_scenes()
    ```

If you need to scaffold a new service, use the [NEW_SERVICE.md](NEW_SERVICE.md) guide.


### Testing

Follow the repository testing guidelines in [TESTING.md](TESTING.md).

! Assume that the test infrastructure is already running by developer (using `docker compose -f docker-compose.test.yaml up --wait`).

When writing tests:
- prefer behavior and contract tests over implementation-detail tests
- use shared test infrastructure
- mock only external systems
- keep tests independent and parallel-safe
- run the relevant pytest command before claiming the change is complete
