from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def ensure_kaggle_credentials() -> None:
    has_env = bool(os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"))
    has_token = bool(os.getenv("KAGGLE_API_TOKEN"))
    has_file = Path.home().joinpath(".kaggle", "kaggle.json").exists()
    if not has_env and not has_token and not has_file:
        raise RuntimeError(
            "Kaggle credentials not found. Set KAGGLE_API_TOKEN or "
            "KAGGLE_USERNAME/KAGGLE_KEY, or create ~/.kaggle/kaggle.json"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public Kaggle dataset files")
    parser.add_argument("--dataset", required=True, help="owner/dataset-slug")
    parser.add_argument("--out", default="data/raw")
    parser.add_argument("--unzip", action="store_true")
    args = parser.parse_args()

    ensure_kaggle_credentials()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    kaggle_bin = Path(sys.executable).with_name("kaggle")
    executable = str(kaggle_bin) if kaggle_bin.exists() else "kaggle"

    cmd = [
        executable,
        "datasets",
        "download",
        "-d",
        args.dataset,
        "-p",
        str(out_dir),
    ]
    if args.unzip:
        cmd.append("--unzip")

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
