#!/usr/bin/env python3
"""Fetch the two pinned upstream dependencies, or verify existing checkouts."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


def check_dependency(name, spec):
    path = ROOT / "deps" / name
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"Dependency {name} is missing or is a symlink; run scripts/bootstrap.py")
    if git(path, "rev-parse", "--show-toplevel") != str(path.resolve()):
        raise ValueError(f"Dependency {name} is not its own checkout")
    if git(path, "rev-parse", "HEAD") != spec["commit"]:
        raise ValueError(f"Dependency {name} differs from the pinned commit")
    if git(path, "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"):
        raise ValueError(f"Dependency {name} has local modifications; refusing to build")
    return spec["commit"]


def check_all():
    lock = json.loads((ROOT / "dependencies.lock.json").read_text())
    return {name: check_dependency(name, spec) for name, spec in lock.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="do not download or alter checkouts")
    args = parser.parse_args()
    lock = json.loads((ROOT / "dependencies.lock.json").read_text())
    for name, spec in lock.items():
        path = ROOT / "deps" / name
        if not path.exists() and not path.is_symlink() and not args.check_only:
            path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "init", str(path)], check=True)
            subprocess.run(["git", "-C", str(path), "remote", "add", "origin", spec["url"]], check=True)
            subprocess.run(["git", "-C", str(path), "fetch", "--depth", "1", "origin", spec["commit"]], check=True)
            subprocess.run(["git", "-C", str(path), "checkout", "--detach", "FETCH_HEAD"], check=True)
        check_dependency(name, spec)
        print(f"Verified {name} at {spec['commit']}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Dependency check failed: {error}", file=sys.stderr)
        sys.exit(1)
