from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _flag_name(key: str) -> str:
    return f"--{key}"


def _build_command(config_path: Path) -> list[str]:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    script = cfg.get("script", "scripts/train_full_sft.py")
    args = cfg.get("args", {})

    cmd: list[str] = [sys.executable, script]
    for key, value in args.items():
        flag = _flag_name(key)
        if isinstance(value, bool):
            if value:
                cmd.append(flag)
            continue
        cmd.extend([flag, str(value)])
    return cmd


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full SFT training from json config")
    parser.add_argument("--config", required=True, help="Path to json config file")
    parser.add_argument("--dry-run", action="store_true", help="Only print the generated command")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    cmd = _build_command(config_path)
    print("Generated command:")
    print(" ".join(cmd))

    if args.dry_run:
        return

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
