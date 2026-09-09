# Agent Protocol — Spec Contract First

This repository is the behavioral source of truth for the linked implementation repository.

## Mandatory startup

Before changing code or specifications, run:

```bash
./scripts/spec-session-start.sh
```

If the sibling code repository is available and you want a full verification pass:

```bash
SPEC_VERIFY_CODE=1 ./scripts/spec-session-start.sh ../insurance-cap-java
```

Then read `.spec-contract/session-context.md` before making changes.

## Contract semantics

- `[published]` scenarios are the current behavioral contract.
- `[proposed]` scenarios describe intended behavior that is not yet part of the published contract.
- Do not silently alter a `[published]` scenario merely to make it match code.
- If requested behavior conflicts with a published scenario, create or revise a `[proposed]` scenario first and make the conflict explicit.
- Keep implementation and tests traceable to the governing spec file and scenario.

## Before a behavioral code change

1. Identify the affected feature files and scenarios.
2. Confirm whether the requested behavior is already `[published]`, already `[proposed]`, or undocumented.
3. If undocumented or conflicting, add/update a `[proposed]` scenario before implementation.
4. Identify affected implementation and tests.

## Before declaring completion

1. Re-run `./scripts/spec-session-start.sh`.
2. Run affected implementation tests; use the full project verification command when practical.
3. Confirm there are no undocumented externally observable behavior changes.
4. Report:
   - affected specs,
   - affected code,
   - affected tests,
   - published/proposed status,
   - preflight result,
   - test result,
   - any remaining drift.

## Fail-closed rules

Stop and report instead of guessing when:

- a published scenario is malformed or duplicated;
- a referenced local test file or named test method is missing;
- requested behavior contradicts a published contract and no proposed change has been recorded;
- the agent cannot determine which spec governs a behavioral change.
