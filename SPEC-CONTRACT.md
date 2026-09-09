# Spec Contract v1

This repository is the behavioral contract for the linked insurance implementation project.

## Session lifecycle

Every coding or specification session should follow:

```text
PREFLIGHT -> WORK -> RECONCILIATION
```

### 1. Preflight

Run:

```bash
./scripts/spec-session-start.sh
```

The command validates all feature files and writes `.spec-contract/session-context.md` containing a contract hash, scenario counts, warnings/errors, and mandatory agent rules.

If the implementation repository is available locally, pass it explicitly:

```bash
./scripts/spec-session-start.sh ../insurance-cap-java
```

To also run the implementation verification suite:

```bash
SPEC_VERIFY_CODE=1 ./scripts/spec-session-start.sh ../insurance-cap-java
```

### 2. Work

- Treat `[published]` as the current contract.
- Treat `[proposed]` as intended but not yet published behavior.
- Never silently rewrite a published scenario because code changed.
- For undocumented behavior changes, record a proposed scenario before implementation.

### 3. Reconciliation

Re-run the preflight, run affected tests, and confirm no undocumented behavioral drift remains.

## What v1 validates

- feature file discovery;
- scenario heading format;
- supported statuses;
- duplicate `(file, title, version)` scenarios;
- published scenarios without test references (warning);
- referenced test files when the code repository is available;
- referenced named test methods when the code repository is available;
- stable SHA-256 contract hash for the readable specifications.

## What v1 deliberately does not do

- It does not automatically modify published specifications to match code.
- It does not infer semantic equivalence between arbitrary Java behavior and prose requirements.
- It does not publish a proposed scenario automatically.
- The CI job in this repository performs spec-only validation because the sibling implementation repository is not checked out by default.

These are deliberate safety boundaries. Semantic code/spec drift detection can be layered on top of the deterministic v1 gate.
