# Run from the repository root, inside the environment that ./dev enters:
# ./dev make check, or make check in the shell that ./dev opens.
#
#   make tangle   tangle the book into build/
#   make check    the checks of the book, Verilator lint and a load of each twin
#   make weave    the reader edition, as build/html/index.html and build/latex/bcw2.pdf
#   make test     the tests of the tools
#   make clean    remove build/
#
# Sphinx runs tools/bcw.py on book/. It checks the book, reports each finding
# at its chapter line, and tangles the code into build/. Each Verilog file is
# linted with build/rtl/bcw_params.sv, the package of PARAMETERs, and each twin
# finds build/model/bcw_params.py through PYTHONPATH. Every location that
# make check prints is a line in the book: the output of Verilator and of each
# twin goes through tools/linemap.py.

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
	done
	@for f in $$(find build/model -name '*.py' | sort); do \
	    PYTHONPATH=build/model $(PY) -c 'import runpy, sys; runpy.run_path(sys.argv[1])' "$$f" 2>&1 | $(MAP) || exit 1; \
	done

# The weave reports findings but does not stop on them: make check is the gate.
weave:
	$(PY) -m sphinx -E -q -b html -c tools book build/html 2>&1 | $(RELATIVE)
	LATEXMKOPTS=-quiet $(PY) -m sphinx -M latexpdf book build -E -q -c tools 2>&1 | $(RELATIVE)

test:
	$(PY) -m pytest

clean:
	rm -rf build
