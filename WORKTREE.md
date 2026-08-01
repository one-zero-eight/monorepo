# Git worktrees

Use worktrees to work on several branches in parallel without stashing or switching in the main checkout.

## Layout

```text
one-zero-eight/
├── monorepo/                 # main worktree — owns settings.yaml
│   └── settings.yaml         # gitignored local config
└── monorepo-<name>/          # extra worktree — uses SETTINGS_PATH
```


## Create a worktree

From the main `monorepo` checkout:

```bash
# new branch
git worktree add ../monorepo-<name> -b <branch>

# existing branch
git worktree add ../monorepo-<name> <branch>

git worktree list
```

Then in the new worktree:

```bash
cd ../monorepo-<name>
uv sync
```

Git hooks from `prek install` already live in the shared `.git/hooks` of the main repo — no need to reinstall per worktree. `SETTINGS_PATH` should already point at the main worktree `settings.yaml`.


## Remove a worktree

```bash
# from main repo
git worktree remove ../monorepo-<name>

# if the directory was deleted manually
git worktree prune
```

`.venv` inside the removed worktree goes away with the directory. Main-worktree `settings.yaml` stays.

## Share config via `SETTINGS_PATH`

App loads settings from `SETTINGS_PATH`, defaulting to `./settings.yaml`:

```python
Path(os.getenv("SETTINGS_PATH", "settings.yaml"))
```

Keep a single `settings.yaml` in the **main** worktree. From that worktree root, export an absolute path (so other worktrees can reuse it):

```bash
# from main monorepo root
export SETTINGS_PATH="$(pwd)/settings.yaml"
```

Persist it in your shell rc, direnv, or IDE run config so every worktree picks it up.

Examples (with `SETTINGS_PATH` already exported):

```bash
# pytest
uv run pytest

# default service port (from src/<service>/__main__.py)
uv run python -m src.maps

# parallel worktrees / agents: override port so instances do not clash
uv run python -m src.maps --port 18009
```

Use a non-default host port per worktree (or per agent) when running the same API in parallel.

Prefer one shared `settings.yaml` via `SETTINGS_PATH`. Exception: schema drift (below).

## Schema drift between worktrees

Shared `SETTINGS_PATH` means **one** file. If a branch changes the pydantic settings schema (`settings.example.yaml` / `config_root_schema.py`) and the shared file no longer validates:

1. **Additive / still compatible** (new optional fields with defaults): update the shared `settings.yaml` once (diff against that branch’s `settings.example.yaml`). Other worktrees keep working.
2. **Breaking** (renamed/removed/required fields): stop sharing for that worktree:
   ```bash
   # in the diverging worktree
   unset SETTINGS_PATH
   cp ../monorepo/settings.yaml ./settings.yaml   # or: uv run scripts/prepare.py
   # edit local settings.yaml for the new schema
   ```
   Run that worktree against `./settings.yaml` until the branch merges. Then fold needed keys back into the main `settings.yaml` and restore `SETTINGS_PATH`.

Do not keep two long-lived divergent shared files — that defeats the point of `SETTINGS_PATH`.


## Do not share `.venv`

Create a separate virtualenv in each worktree with `uv sync`.

Reasons:

- venv embeds absolute paths
- branches may differ in lockfile / dependencies
- editable installs point at a specific source tree

Package caches (`~/.cache/uv`) are already shared by uv — that is enough.

## Docker

Options:

1. **Preferred:** set up infra from the **main** worktree. Use extra worktrees for code + `uv run` with `SETTINGS_PATH`.
2. **Isolated stack in an extra worktree:** either place/copy a `settings.yaml` there for the mount, or run Compose only from main. If you spin a second stack, use a distinct project name, e.g. `COMPOSE_PROJECT_NAME=monorepo-foo`. However, most probably it is not needed as we prefer to run services locally on host machine via `uv run`.
