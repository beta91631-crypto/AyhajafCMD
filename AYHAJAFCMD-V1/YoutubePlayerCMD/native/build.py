"""Build renderer.exe on Windows or a native renderer on Unix-like systems."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    native_dir = root / "native"
    output_dir = root / "bin"
    output_dir.mkdir(exist_ok=True)
    executable = output_dir / ("renderer.exe" if os.name == "nt" else "renderer")
    marker = output_dir / ".renderer-source-hash"
    sources = sorted((native_dir / "src").glob("*.cpp"))
    headers = sorted((native_dir / "src").glob("*.hpp"))
    digest = hashlib.sha256()
    for source in sources + headers:
        digest.update(source.relative_to(root).as_posix().encode("ascii"))
        digest.update(source.read_bytes())
    source_hash = digest.hexdigest()
    if executable.exists() and marker.exists() and marker.read_text() == source_hash:
        print(f"Native renderer is up to date: {executable}")
        return 0

    compiler = shutil.which("g++")
    vswhere = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / \
        "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if os.name == "nt" and (shutil.which("cl") or vswhere.exists()):
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(native_dir / "build_msvc.bat")],
            cwd=root,
            check=False,
        )
    elif compiler:
        command = [
            compiler, "-O2", "-Wall", "-Wextra", "-std=c++17",
            *(str(source) for source in sources), "-o", str(executable),
        ]
        if os.name == "nt":
            command.insert(1, "-static")
        result = subprocess.run(command, cwd=root, check=False)
    else:
        print("No supported C++ compiler found. Install MSVC Build Tools or MinGW-w64.", file=sys.stderr)
        return 1

    if result.returncode != 0 or not executable.exists():
        print("Native renderer build failed.", file=sys.stderr)
        return result.returncode or 1
    marker.write_text(source_hash, encoding="ascii")
    print(f"Built native renderer: {executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())