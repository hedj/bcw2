"""Tangle the book with entangled, then end every tangled file with a newline.

Entangled 2.1.13 omits the final newline when it creates a file (Create.run in
its transaction.py), but not when it rewrites one. Verilator -Wall rejects a
file without it (EOFNEWLINE). Entangled hashes a file without its trailing
whitespace, so the added newline does not count as a hand edit.

Run it from the repository root: .venv/bin/python tools/tangle.py
"""

import json
import subprocess
import sys
from pathlib import Path


def add_final_newlines(root):
    """End each file that entangled tangled under root with a newline.

    Returns the list of files that it changed.
    """
    root = Path(root)
    db = json.loads((root / ".entangled" / "filedb.json").read_text())
    changed = []
    for name in db["target"]:
        path = root / name
        text = path.read_bytes()
        if text and not text.endswith(b"\n"):
            path.write_bytes(text + b"\n")
            changed.append(name)
    return changed


def main():
    entangled = Path(sys.executable).parent / "entangled"
    subprocess.run([str(entangled), "tangle"], check=True)
    add_final_newlines(".")


if __name__ == "__main__":
    main()
