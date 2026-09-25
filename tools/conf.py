"""The Sphinx configuration of the book. The Makefile runs sphinx-build -c tools on book/."""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

project = "BCW-2 Soubou"
root_doc = "index"
extensions = ["bcw"]
# Each finding already names its check, so Sphinx does not add its type.
show_warning_types = False

bcw_tools = [str(path) for path in sorted(TOOLS.glob("*.py"))]
bcw_general_words = str(ROOT / "book" / "general-words.txt")
bcw_retired_anchors = str(ROOT / "book" / "retired-anchors.txt")
bcw_tangle_root = str(ROOT)
bcw_summary = True
