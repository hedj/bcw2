#!/bin/sh
# The one toolchain definition. Run it from the repository root, once per
# clone or container: sh tools/setup.sh
#
# It installs the pinned Python tools into .venv/ and makes sure that
# Verilator, Icarus Verilog and TeX Live are the pinned versions. make weave
# needs TeX Live for the PDF. On a system with apt-get, it installs these
# tools, and TeX Live without its recommended packages. On any other system,
# install them yourself at these versions, then run this script again.
# It also points Git at tools/hooks, so that the pre-push hook runs.
set -e

VERILATOR_VERSION=5.020
IVERILOG_VERSION=12.0
TEXLIVE_YEAR=2023
TEXLIVE_PACKAGE=2023.20240207-1
LATEXMK_VERSION=4.83

cd "$(dirname "$0")/.."

python3 -m venv .venv
.venv/bin/pip install --quiet --require-hashes -r tools/requirements.txt

have_versions() {
    verilator --version 2>/dev/null | grep -q "^Verilator $VERILATOR_VERSION " &&
        iverilog -V 2>/dev/null | head -n 1 | grep -q "version $IVERILOG_VERSION " &&
        pdflatex --version 2>/dev/null | head -n 1 | grep -q "(TeX Live $TEXLIVE_YEAR" &&
        latexmk --version 2>/dev/null | grep -q "Version $LATEXMK_VERSION\$"
}

if ! have_versions; then
    if command -v apt-get >/dev/null 2>&1; then
        SUDO=
        [ "$(id -u)" = 0 ] || SUDO=sudo
        $SUDO apt-get install -y -q "verilator=$VERILATOR_VERSION-1" "iverilog=$IVERILOG_VERSION-2build2"
        $SUDO apt-get install -y -q --no-install-recommends "latexmk=1:$LATEXMK_VERSION-1" \
            "texlive-latex-recommended=$TEXLIVE_PACKAGE" "texlive-latex-extra=$TEXLIVE_PACKAGE" \
            "texlive-fonts-recommended=$TEXLIVE_PACKAGE"
    fi
fi

if ! have_versions; then
    echo "setup: need Verilator $VERILATOR_VERSION, Icarus Verilog $IVERILOG_VERSION," \
        "TeX Live $TEXLIVE_YEAR and latexmk $LATEXMK_VERSION." >&2
    echo "setup: found: $(verilator --version 2>&1 | head -n 1); $(iverilog -V 2>&1 | head -n 1);" \
        "$(pdflatex --version 2>&1 | head -n 1); $(latexmk --version 2>&1 | tail -n 1)" >&2
    exit 1
fi

git config core.hooksPath tools/hooks

echo "setup: toolchain ready"
echo "  $(.venv/bin/python --version)"
echo "  Sphinx $(.venv/bin/python -c 'import sphinx; print(sphinx.__version__)')"
echo "  docutils $(.venv/bin/python -c 'import docutils; print(docutils.__version__)')"
echo "  z3 $(.venv/bin/python -c 'import z3; print(z3.get_version_string())')"
echo "  $(verilator --version)"
echo "  $(iverilog -V 2>&1 | head -n 1)"
echo "  $(pdflatex --version | head -n 1)"
echo "  $(latexmk --version | tail -n 1)"
