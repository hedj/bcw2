# Run from the repository root, inside the environment that ./dev enters:
# ./dev make check, or make check in the shell that ./dev opens.
#
#   make tangle   tangle the book into build/
#   make check    the checks of the book, Verilator lint, a read by yosys, and a run of each
#                 check directive
#   make weave    the reader edition, as build/html/index.html and build/latex/bcw2.pdf
#   make test     the tests of the tools, with pytest on each core
#   make clean    remove build/
#
# Sphinx runs tools/bcw.py on book/. It checks the book, reports each finding
# at its chapter line, and tangles the code into build/. Each Verilog file is
# linted with build/rtl/bcw_params.sv, the package of PARAMETERs, and read by
# yosys, which the formal checks use. No tool runs a twin: tools/bcw.py and
# tools/run_checks.py translate each twin with tools/twin.py. tools/run_checks.py
# then runs each check directive that build/checks.json lists. Every location that
# make check prints is a line in the book: the output of Verilator and of each
# check goes through tools/linemap.py, which reads build/tangle.json.

# make finds bash on the PATH of the environment. NixOS has no /bin/bash.
SHELL := bash
.SHELLFLAGS := -o pipefail -c
PY := python3
MAP := $(PY) tools/linemap.py
# -E reads every chapter, because Sphinx does not report again on a chapter
# that it read in an earlier build. sed shortens the paths that docutils prints.
SPHINX := $(PY) -m sphinx -E -q -b dummy -c tools book build/sphinx
RELATIVE := sed "s|$(CURDIR)/||"

ifndef BCW_ENV
$(error the tools come from the Nix environment: run ./dev make $(MAKECMDGOALS))
endif

.PHONY: tangle check weave test clean

tangle:
	$(SPHINX) 2>&1 | $(RELATIVE)

check:
	$(SPHINX) -W --keep-going 2>&1 | $(RELATIVE)
	@for f in $$(find build/rtl -name '*.v' | sort); do \
	    verilator --lint-only --quiet-stats -Wall build/rtl/bcw_params.sv "$$f" 2>&1 | $(MAP) || exit 1; \
	    yosys -q -p "read_verilog -sv build/rtl/bcw_params.sv $$f" 2>&1 | $(MAP) || exit 1; \
	done
	$(PY) tools/run_checks.py

# The weave reports findings but does not stop on them: make check is the gate.
weave:
	$(PY) -m sphinx -E -q -b html -c tools book build/html 2>&1 | $(RELATIVE)
	LATEXMKOPTS=-quiet $(PY) -m sphinx -M latexpdf book build -E -q -c tools 2>&1 | $(RELATIVE)

test:
	$(PY) -m pytest -n auto

clean:
	rm -rf build
