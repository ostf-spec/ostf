#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bootstrap isolated, hash-pinned tools and run the OSTF 0.3 reader checks."""
import hashlib
import pathlib
import subprocess
import sys
import urllib.request
import venv

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ENVIRONMENT = ROOT / ".venv"
# The OASIS SARIF 2.1.0 schema (Errata 01) that check.py validates SARIF output against (Annex D),
# fetched once and pinned by digest like the Python dependencies.
SARIF_SCHEMA = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"
SARIF_SHA256 = "c3b4bb2d6093897483348925aaa73af03b3e3f4bd4ca38cef26dcb4212a2682e"


def main():
    if sys.version_info < (3, 12):
        raise SystemExit("OSTF conformance needs Python 3.12 or newer, whose parser reads the syntax of Annex L")
    python = ENVIRONMENT / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    digest = hashlib.sha256((HERE / "requirements.txt").read_bytes()).hexdigest()
    marker = ENVIRONMENT / "ostf-requirements.sha256"
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(ENVIRONMENT)
    if not marker.is_file() or marker.read_text().strip() != digest:
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "--require-hashes", "-r", str(HERE / "requirements.txt")], check=True)
        marker.write_text(digest + "\n")
    schema = ENVIRONMENT / "sarif-schema-2.1.0.json"
    if not schema.is_file():
        with urllib.request.urlopen(SARIF_SCHEMA, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != SARIF_SHA256:
            raise SystemExit(f"the SARIF schema at {SARIF_SCHEMA} is not the pinned one")
        schema.write_bytes(data)
    subprocess.run([str(python), str(HERE / "check.py")], cwd=ROOT, check=True)
    subprocess.run([str(python), str(HERE.parent / "tools" / "check_tools.py")], cwd=ROOT, check=True)
    # The trials, which need the lock, stay as they ran: reproducible at the tag doc-0.15 (plan, section 8), not run here.


if __name__ == "__main__":
    main()
