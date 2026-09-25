#!/bin/sh
# The one toolchain definition. Run it from the repository root, once per
# clone or container: sh tools/setup.sh
#
# It installs the pinned Python tools into .venv/ and makes sure that
# Verilator and Icarus Verilog are the pinned versions. On a system with
# apt-get, it installs the two Verilog tools. On any other system, install
# them yourself at these versions, then run this script again.
set -e

VERILATOR_VERSION=5.020
IVERILOG_VERSION=12.0

cd "$(dirname "$0")/.."

python3 -m venv .venv
.venv/bin/pip install --quiet --require-hashes -r tools/requirements.txt

have_versions() {
    verilator --version 2>/dev/null | grep -q "^Verilator $VERILATOR_VERSION " &&
        iverilog -V 2>/dev/null | head -n 1 | grep -q "version $IVERILOG_VERSION "
}

if ! have_versions; then
    if command -v apt-get >/dev/null 2>&1; then
        SUDO=
        [ "$(id -u)" = 0 ] || SUDO=sudo
        $SUDO apt-get install -y -q "verilator=$VERILATOR_VERSION-1" "iverilog=$IVERILOG_VERSION-2build2"
    fi
fi

if ! have_versions; then
    echo "setup: need Verilator $VERILATOR_VERSION and Icarus Verilog $IVERILOG_VERSION." >&2
    echo "setup: found: $(verilator --version 2>&1 | head -n 1); $(iverilog -V 2>&1 | head -n 1)" >&2
    exit 1
fi

echo "setup: toolchain ready"
echo "  $(.venv/bin/python --version)"
echo "  entangled $(.venv/bin/pip show entangled-cli | sed -n 's/^Version: //p')"
echo "  markdown-it-py $(.venv/bin/pip show markdown-it-py | sed -n 's/^Version: //p')"
echo "  z3 $(.venv/bin/python -c 'import z3; print(z3.get_version_string())')"
echo "  $(verilator --version)"
echo "  $(iverilog -V 2>&1 | head -n 1)"
