#!/usr/bin/env python3
"""Spec Contract preflight.

Validates the human-readable SpecDriven feature contract and, when the sibling
code repository is available, verifies that published test references still
point to real files and named test methods.

No third-party dependencies are required.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

SCENARIO_RE = re.compile(
    r"^##\s+(?P<title>.+?)\s+@v(?P<version>\d+)\s+\[(?P<status>[A-Za-z_-]+)\]\s*$"
)
TEST_RE = re.compile(
    r"\[test:\s*(?:(?P<method>[A-Za-z_$][A-Za-z0-9_$]*)\s*:\s*)?"
    r"(?P<url>https?://[^\]\s]+)\s*\]"
)


@dataclass
class TestRef:
    method: str | None
    url: str
    line: int


@dataclass
class Scenario:
    path: str
    title: str
    version: int
    status: str
    line: int
    tests: list[TestRef]

    @property
    def key(self) -> str:
        return f"{self.path}::{self.title}::v{self.version}"


def load_config(spec_root: Path) -> dict:
    path = spec_root / "spec-contract.json"
    if not path.exists():
        raise SystemExit(f"spec-contract.json not found under {spec_root}")
    return json.loads(path.read_text(encoding="utf-8"))


def excluded(rel: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(rel, pattern) for pattern in patterns)


def feature_files(spec_root: Path, config: dict) -> list[Path]:
    found: dict[str, Path] = {}
    excludes = config.get("exclude_globs", [])
    for pattern in config.get("spec_globs", ["**/*.feature.md"]):
        for path in spec_root.glob(pattern):
            if not path.is_file():
                continue
            rel = path.relative_to(spec_root).as_posix()
            if excluded(rel, excludes):
                continue
            found[rel] = path
    return [found[k] for k in sorted(found)]


def parse_scenarios(path: Path, spec_root: Path, allowed_statuses: set[str]):
    rel = path.relative_to(spec_root).as_posix()
    lines = path.read_text(encoding="utf-8").splitlines()
    scenarios: list[Scenario] = []
    errors: list[str] = []

    headings: list[tuple[int, re.Match[str]]] = []
    for i, line in enumerate(lines, start=1):
        if not line.startswith("## "):
            continue
        match = SCENARIO_RE.match(line)
        looks_like_scenario = "@v" in line or "[published]" in line or "[proposed]" in line
        if not match:
            if looks_like_scenario:
                errors.append(f"{rel}:{i}: malformed scenario heading: {line}")
            continue
        if match.group("status") not in allowed_statuses:
            errors.append(
                f"{rel}:{i}: unsupported status [{match.group('status')}]; "
                f"allowed={sorted(allowed_statuses)}"
            )
        headings.append((i, match))

    for idx, (line_no, match) in enumerate(headings):
        end = headings[idx + 1][0] - 1 if idx + 1 < len(headings) else len(lines)
        body = "\n".join(lines[line_no:end])
        tests = [
            TestRef(method=m.group("method"), url=m.group("url"), line=line_no + body[: m.start()].count("\n") + 1)
            for m in TEST_RE.finditer(body)
        ]
        scenarios.append(
            Scenario(
                path=rel,
                title=match.group("title").strip(),
                version=int(match.group("version")),
                status=match.group("status"),
                line=line_no,
                tests=tests,
            )
        )
    return scenarios, errors


def discover_code_root(spec_root: Path, config: dict, explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        return p if p.exists() else None
    for candidate in config.get("code_repo_candidates", []):
        p = (spec_root / candidate).resolve()
        if p.exists():
            return p
    return None


def contract_hash(paths: list[Path], spec_root: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        rel = path.relative_to(spec_root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def validate_code_links(
    scenarios: list[Scenario], code_root: Path, config: dict, errors: list[str], warnings: list[str]
) -> None:
    prefix = config.get("test_link_prefix", "")
    policy = config.get("policy", {})
    for scenario in scenarios:
        for ref in scenario.tests:
            if not prefix or not ref.url.startswith(prefix):
                warnings.append(
                    f"{scenario.path}:{ref.line}: external test URL not checked locally: {ref.url}"
                )
                continue
            rel = ref.url[len(prefix) :].split("#", 1)[0]
            target = code_root / rel
            if not target.is_file():
                msg = f"{scenario.path}:{ref.line}: test target missing: {rel}"
                if policy.get("fail_on_missing_local_test_target", True):
                    errors.append(msg)
                else:
                    warnings.append(msg)
                continue
            if ref.method:
                text = target.read_text(encoding="utf-8", errors="replace")
                method_re = re.compile(rf"\b{re.escape(ref.method)}\s*\(")
                if not method_re.search(text):
                    msg = (
                        f"{scenario.path}:{ref.line}: named test method '{ref.method}' "
                        f"not found in {rel}"
                    )
                    if policy.get("fail_on_missing_named_test_method", True):
                        errors.append(msg)
                    else:
                        warnings.append(msg)


def render_context(report: dict) -> str:
    lines = [
        "# Spec Contract Session Context",
        "",
        f"Contract hash: `{report['contract_hash']}`",
        f"Feature files: **{report['feature_files']}**",
        f"Scenarios: **{report['scenarios']}**",
        f"Published: **{report['published']}**",
        f"Proposed: **{report['proposed']}**",
        f"Code repository: `{report.get('code_root') or 'not available'}`",
        f"Status: **{'PASS' if report['ok'] else 'FAIL'}**",
        "",
        "## Mandatory agent behavior",
        "",
        "1. Treat `[published]` scenarios as the current behavioral contract.",
        "2. Before changing externally observable behavior, create or update a `[proposed]` scenario first.",
        "3. Do not silently rewrite a `[published]` scenario to match code.",
        "4. Keep implementation and tests traceable to the governing spec file.",
        "5. Run this preflight again after the work and run the affected code tests before declaring completion.",
    ]
    if report["errors"]:
        lines += ["", "## Errors", ""] + [f"- {x}" for x in report["errors"]]
    if report["warnings"]:
        lines += ["", "## Warnings", ""] + [f"- {x}" for x in report["warnings"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SpecDriven contract before an agent/code session")
    parser.add_argument("--spec-root", default=".", help="spec repository root")
    parser.add_argument("--code-root", help="sibling code repository root")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--write-context", help="write agent-readable Markdown session context")
    args = parser.parse_args()

    spec_root = Path(args.spec_root).expanduser().resolve()
    config = load_config(spec_root)
    policy = config.get("policy", {})
    files = feature_files(spec_root, config)
    allowed = set(config.get("scenario_statuses", ["published", "proposed"]))

    scenarios: list[Scenario] = []
    errors: list[str] = []
    warnings: list[str] = []
    for path in files:
        parsed, parse_errors = parse_scenarios(path, spec_root, allowed)
        scenarios.extend(parsed)
        errors.extend(parse_errors)

    seen: dict[str, Scenario] = {}
    for scenario in scenarios:
        if scenario.key in seen:
            msg = (
                f"duplicate scenario {scenario.key} at {scenario.path}:{scenario.line}; "
                f"first seen at {seen[scenario.key].path}:{seen[scenario.key].line}"
            )
            if policy.get("fail_on_duplicate_scenario", True):
                errors.append(msg)
            else:
                warnings.append(msg)
        else:
            seen[scenario.key] = scenario

        if scenario.status == "published" and not scenario.tests:
            warnings.append(
                f"{scenario.path}:{scenario.line}: published scenario has no [test: ...] traceability reference"
            )

    code_root = discover_code_root(spec_root, config, args.code_root)
    if args.code_root and code_root is None:
        errors.append(f"explicit code repository does not exist: {args.code_root}")
    elif code_root is None:
        warnings.append("code repository not found; ran spec-only checks")
    else:
        validate_code_links(scenarios, code_root, config, errors, warnings)

    report = {
        "ok": not errors,
        "contract_hash": contract_hash(files, spec_root),
        "feature_files": len(files),
        "scenarios": len(scenarios),
        "published": sum(1 for s in scenarios if s.status == "published"),
        "proposed": sum(1 for s in scenarios if s.status == "proposed"),
        "code_root": str(code_root) if code_root else None,
        "errors": errors,
        "warnings": warnings,
        "scenario_index": [
            {
                **{k: v for k, v in asdict(s).items() if k != "tests"},
                "tests": [asdict(t) for t in s.tests],
            }
            for s in scenarios
        ],
    }

    if args.write_context:
        out = Path(args.write_context)
        if not out.is_absolute():
            out = spec_root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_context(report), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        state = "PASS" if report["ok"] else "FAIL"
        print(f"SPEC CONTRACT: {state}")
        print(
            f"files={report['feature_files']} scenarios={report['scenarios']} "
            f"published={report['published']} proposed={report['proposed']}"
        )
        print(f"contract_hash={report['contract_hash']}")
        print(f"code_root={report['code_root'] or 'not available'}")
        for item in warnings:
            print(f"WARN: {item}")
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
