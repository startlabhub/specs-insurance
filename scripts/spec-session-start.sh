#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="$ROOT/.spec-contract/session-context.md"
CODE_ROOT="${1:-}"

ARGS=(--spec-root "$ROOT" --write-context "$CONTEXT")
if [[ -n "$CODE_ROOT" ]]; then
  ARGS+=(--code-root "$CODE_ROOT")
fi

python3 "$ROOT/scripts/spec-preflight.py" "${ARGS[@]}"

echo
echo "Agent context written to: $CONTEXT"
echo "Read it before changing code or specifications."

if [[ "${SPEC_VERIFY_CODE:-0}" == "1" ]]; then
  if [[ -z "$CODE_ROOT" ]]; then
    for candidate in "$ROOT/../insurance-java" "$ROOT/../insurance-cap-java"; do
      if [[ -d "$candidate" ]]; then
        CODE_ROOT="$candidate"
        break
      fi
    done
  fi
  if [[ -z "$CODE_ROOT" || ! -d "$CODE_ROOT" ]]; then
    echo "error: SPEC_VERIFY_CODE=1 but no code repository was found" >&2
    exit 1
  fi
  echo
  echo "Running code verification in: $CODE_ROOT"
  (cd "$CODE_ROOT" && ./mvnw verify)
fi
