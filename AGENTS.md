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

For parallel branches via git worktrees, see [WORKTREE.md](WORKTREE.md).


### Git

When finishing a task with code changes:
- stage only the relevant changes (not the full working tree / unrelated diffs); do not stage secrets (`.env`, credentials, local `settings.yaml`)
- draft a concise conventional commit message matching recent `git log` style (focus on why). **Always include a scope:**
  - service/area scope when the change is local (e.g. `feat(maps): …`, `fix(schedule): …`)
  - comma-separated scopes when a few services are touched (e.g. `chore(schedule, maps): …`)
  - `general` for repo-wide / all-services changes (e.g. `chore(general): …`, `docs(general): …`)
- **Base the message on the full staged diff** (`git diff --cached` / all files being committed), not only the last edit in the chat. One commit = one message that covers the whole staged set.
- if the change is tied to a GitHub issue, put a trailer in the commit body: `Closes one-zero-eight/monorepo#123` when the commit closes the issue, or `Relates one-zero-eight/monorepo#123` when it only relates to it
- propose that message to the IDE Source Control input by writing it to `.scm-commit-msg` at the repo root (gitignored — do not stage it). Requires the SCM Commit Message extension in `tools/scm-commit-msg-from-file` (install once per machine into `~/.cursor/extensions/local.scm-commit-msg-from-file-<version>/`, then Reload Window). After an IDE commit the extension clears the SCM input only when it still matches `.scm-commit-msg`, then deletes the file. After a CLI commit, always `rm -f .scm-commit-msg` (the extension then clears the matching SCM input).
- do **not** run `git commit` unless the user explicitly asks


### Testing

Follow the repository testing guidelines in [TESTING.md](TESTING.md).

! Assume that the test infrastructure is already running by developer (using `docker compose -f docker-compose.test.yaml up --wait`).

When writing tests:
- prefer behavior and contract tests over implementation-detail tests
- use shared test infrastructure
- mock only external systems
- keep tests independent and parallel-safe
- run the relevant pytest command before claiming the change is complete
