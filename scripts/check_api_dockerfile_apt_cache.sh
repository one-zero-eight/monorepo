#!/usr/bin/env bash
# Verify whether the builder-stage apt-get layer in api.Dockerfile is reused.
#
# Modes (what "between runs" means):
#   consecutive   — two back-to-back builds on the same machine (local layer cache)
#   fresh-runner  — prune build cache between builds (simulates CI without cache hit)
#
# Usage:
#   ./scripts/check_api_dockerfile_apt_cache.sh                  # consecutive (default)
#   ./scripts/check_api_dockerfile_apt_cache.sh --fresh-runner   # CI-like, no cache carry-over
#
# Exit codes:
#   0 — second build reused apt (layer CACHED or apt cache mount on fresh-runner)
#   1 — apt-get RUN layer rebuilt without apt cache benefit
#   2 — script/parse error

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKERFILE="${DOCKERFILE:-$ROOT/api.Dockerfile}"
TARGET="${TARGET:-builder}"
TAG_PREFIX="${TAG_PREFIX:-api-dockerfile-apt-cache-check}"
MODE="${MODE:-consecutive}"
APT_STEP_HINT='apt-get update && apt-get install'
# Rebuild faster than this ⇒ BuildKit apt cache mount is working (fresh-runner).
APT_REBUILD_MAX_SECS="${APT_REBUILD_MAX_SECS:-15}"

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fresh-runner)
      MODE=fresh-runner
      shift
      ;;
    --consecutive)
      MODE=consecutive
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT"

if ! docker info >/dev/null 2>&1; then
  echo "error: docker daemon not available" >&2
  exit 2
fi

build_log="$(mktemp)"
trap 'rm -f "$build_log"' EXIT

run_build() {
  local tag=$1
  shift
  : >"$build_log"
  echo "==> docker build --target $TARGET -t $tag $* (logging to temp file)"
  if ! docker build \
    --progress=plain \
    -f "$DOCKERFILE" \
    --target "$TARGET" \
    -t "$tag" \
    "$@" \
    . >"$build_log" 2>&1; then
    echo "error: docker build failed" >&2
    cat "$build_log" >&2
    exit 2
  fi
}

apt_step_status() {
  # Find the BuildKit step that runs the builder apt-get install line.
  local step_id=""
  local cached=0
  local rebuilt=0
  local rebuild_secs=""

  while IFS= read -r line; do
    if [[ "$line" =~ ^#([0-9]+)\  ]] && [[ "$line" == *"RUN"* ]] && [[ "$line" == *"apt-get update"* ]] && [[ "$line" == *"apt-get install"* ]]; then
      step_id="${BASH_REMATCH[1]}"
      cached=0
      rebuilt=0
      rebuild_secs=""
      continue
    fi
    if [[ -z "$step_id" ]]; then
      continue
    fi
    if [[ "$line" == "#$step_id CACHED" ]]; then
      cached=1
    elif [[ "$line" =~ ^#$step_id\ DONE\ ([0-9.]+)s ]]; then
      rebuilt=1
      rebuild_secs="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ ^#([0-9]+)\  ]] && [[ "${BASH_REMATCH[1]}" != "$step_id" ]]; then
      if (( cached || rebuilt )); then
        break
      fi
      step_id=""
    fi
  done <"$build_log"

  if [[ -z "$step_id" ]]; then
    echo "parse_error"
    return
  fi
  if (( cached )); then
    echo "cached"
  elif (( rebuilt )); then
    if [[ -n "$rebuild_secs" ]]; then
      echo "rebuilt:${rebuild_secs}"
    else
      echo "rebuilt"
    fi
  else
    echo "unknown"
  fi
}

show_apt_step_lines() {
  grep -E "RUN.*apt-get update|#([0-9]+) (CACHED|DONE)" "$build_log" \
    | grep -B0 -A1 "apt-get update" \
    | head -20 || true
  echo "---"
  awk '
    /RUN apt-get update && apt-get install/ { show=1 }
    show { print }
    show && /^#[0-9]+ (CACHED|DONE)/ { exit }
  ' "$build_log"
}

echo "Dockerfile: $DOCKERFILE"
echo "Target:     $TARGET"
echo "Mode:       $MODE"
echo

if [[ "$MODE" == "fresh-runner" ]]; then
  echo "==> clearing layer cache before warmup: docker builder prune -af --filter type=regular"
  docker builder prune -af --filter type=regular >/dev/null
fi

run_build "${TAG_PREFIX}:warmup"
warmup_status="$(apt_step_status)"
echo "Warmup build apt layer: $warmup_status"

if [[ "$MODE" == "fresh-runner" ]]; then
  echo "==> simulating layer-cache miss: docker builder prune -af --filter type=regular"
  docker builder prune -af --filter type=regular >/dev/null
fi
echo

run_build "${TAG_PREFIX}:check"
check_status="$(apt_step_status)"

echo "Second build apt layer: $check_status"
echo
echo "Relevant build log excerpt:"
show_apt_step_lines
echo

case "$check_status" in
  cached)
    echo "PASS: apt-get layer was reused from cache on the second build."
    exit 0
    ;;
  rebuilt:*)
    rebuild_secs="${check_status#rebuilt:}"
    if [[ "$MODE" == "fresh-runner" ]] \
      && awk -v s="$rebuild_secs" -v max="$APT_REBUILD_MAX_SECS" 'BEGIN { exit !(s+0 < max+0) }'; then
      echo "PASS: layer rebuilt in ${rebuild_secs}s but apt cache mount reused packages (<${APT_REBUILD_MAX_SECS}s)."
      exit 0
    fi
    echo "FAIL: apt-get layer rebuilt in ${rebuild_secs:-?}s without layer or apt cache reuse."
    exit 1
    ;;
  rebuilt)
    echo "FAIL: apt-get layer was rebuilt on the second build (not cached)."
    exit 1
    ;;
  parse_error)
    echo "ERROR: could not find apt-get RUN step in build log." >&2
    exit 2
    ;;
  *)
    echo "ERROR: could not determine cache status (got: $check_status)." >&2
    exit 2
    ;;
esac
