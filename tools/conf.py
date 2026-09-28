"""The Sphinx configuration of the book. The Makefile runs sphinx-build -c tools on book/."""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

project = "BCW-2 Soubou"
author = "J. Hedditch"
copyright = "2026, J. Hedditch"
root_doc = "index"
extensions = ["bcw", "weave"]
latex_documents = [(root_doc, "bcw2.tex", project, author, "manual")]
latex_engine = "pdflatex"
# The margins of 0.5 in hold the running header and footer too, or they would reach the edge.
latex_elements = {"geometry": r"\usepackage[includeheadfoot]{geometry}",
                  "sphinxsetup": "hmargin=0.5in, vmargin=0.5in"}
# Each finding already names its check, so Sphinx does not add its type.
show_warning_types = False

bcw_tools = [str(path) for path in sorted(TOOLS.glob("*.py"))]
bcw_tests = [str(path) for path in sorted([*(TOOLS / "tests").glob("*.py"), *(TOOLS / "tests" / "cases").glob("*.toml")])]
bcw_general_words = str(ROOT / "book" / "general-words.txt")
bcw_retired_anchors = str(ROOT / "book" / "retired-anchors.txt")
bcw_tangle_root = str(ROOT)
bcw_summary = True
