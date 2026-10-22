#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bootstrap isolated, hash-pinned tools and run standalone draft checks."""
import hashlib
import pathlib
import subprocess
import sys
import venv

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
ENVIRONMENT = ROOT / ".venv"


def main():
    if sys.version_info < (3, 10):
        raise SystemExit("OSTF conformance needs Python 3.10 or newer")
    python = ENVIRONMENT / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    digest = hashlib.sha256((HERE / "requirements.txt").read_bytes()).hexdigest()
    marker = ENVIRONMENT / "ostf-requirements.sha256"
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(ENVIRONMENT)
    if not marker.is_file() or marker.read_text().strip() != digest:
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "--require-hashes", "-r", str(HERE / "requirements.txt")], check=True)
        marker.write_text(digest + "\n")
    subprocess.run([str(python), str(HERE / "check.py")], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
