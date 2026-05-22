#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_ROOT.parents[1]
BENCHMARK_SCRIPT = SCRIPT_ROOT / "benchmark_live_api.py"

PROFILE_PRESETS: dict[str, list[str]] = {
    "performance": [
        "--runs",
        "2",
        "--output",
        str(PROJECT_ROOT / "docs" / "performance-baseline.json"),
    ],
    "load-2x": [
        "--runs",
        "2",
        "--concurrency",
        "2",
        "--output",
        str(PROJECT_ROOT / "docs" / "load-baseline.json"),
    ],
    "stress-3x": [
        "--runs",
        "3",
        "--concurrency",
        "3",
        "--resource-profile",
        "docker",
        "--resource-interval",
        "1.0",
        "--output",
        str(PROJECT_ROOT / "docs" / "stress-baseline.json"),
    ],
    "stress-4x": [
        "--runs",
        "4",
        "--concurrency",
        "4",
        "--resource-profile",
        "hybrid",
        "--resource-interval",
        "1.0",
        "--output",
        str(PROJECT_ROOT / "docs" / "stress-4x-baseline.json"),
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a named benchmark profile against the XAI Report Builder API.")
    parser.add_argument("profile", choices=sorted(PROFILE_PRESETS))
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="ChangeMe123!")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--host-process-match", default="ollama")
    parser.add_argument("--host-resource-alias", default="host_ollama")
    parser.add_argument("--pipeline-timeout", type=float, default=240.0)
    parser.add_argument("--request-timeout", type=float, default=60.0)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--include-resource-samples", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _profile_args(profile: str, *, output_override: Path | None) -> list[str]:
    profile_args = list(PROFILE_PRESETS[profile])
    if output_override is None:
        return profile_args

    for index, value in enumerate(profile_args[:-1]):
        if value == "--output":
            profile_args[index + 1] = str(output_override)
            return profile_args
    profile_args.extend(["--output", str(output_override)])
    return profile_args


def build_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(BENCHMARK_SCRIPT),
        "--base-url",
        args.base_url,
        "--email",
        args.email,
        "--password",
        args.password,
        "--pipeline-timeout",
        str(args.pipeline_timeout),
        "--request-timeout",
        str(args.request_timeout),
        "--poll-interval",
        str(args.poll_interval),
        "--host-process-match",
        args.host_process_match,
        "--host-resource-alias",
        args.host_resource_alias,
        *_profile_args(args.profile, output_override=args.output),
    ]
    if args.include_resource_samples:
        command.append("--include-resource-samples")
    return command


def main() -> int:
    args = parse_args()
    command = build_command(args)
    print(" ".join(command))
    if args.dry_run:
        return 0
    result = subprocess.run(command, check=False)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
