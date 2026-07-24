from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    available: bool
    detail: str


def command(name: str, arguments: list[str]) -> Check:
    executable = shutil.which(arguments[0])
    if executable is None:
        return Check(name, False, f"{arguments[0]} is not on PATH")
    result = subprocess.run(  # noqa: S603 - fixed diagnostic commands only
        arguments,
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    lines = (result.stdout or result.stderr).strip().splitlines()
    return Check(name, result.returncode == 0, lines[0] if lines else executable)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    checks = [
        Check("Python", sys.version_info >= (3, 12), sys.version.split()[0]),
        command("uv", ["uv", "--version"]),
        command("Git", ["git", "--version"]),
        command("k6", ["k6", "version"]),
        command("Node", ["node", "--version"]),
        command("pnpm", ["pnpm.cmd" if sys.platform == "win32" else "pnpm", "--version"]),
        Check("pyproject", (root / "pyproject.toml").is_file(), "pyproject.toml"),
        Check("pnpm lock", (root / "pnpm-lock.yaml").is_file(), "pnpm-lock.yaml"),
        Check("uv lock", (root / "uv.lock").is_file(), "uv.lock"),
    ]
    print(json.dumps([asdict(item) for item in checks], indent=2))
    return 0 if all(item.available for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
