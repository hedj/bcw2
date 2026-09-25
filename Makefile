# Run from the repository root, after sh tools/setup.sh.
#
#   make tangle   tangle the book into build/
#   make check    the checks of the book, Verilator lint and a load of each twin
#   make weave    the reader edition, as build/html/index.html and build/latex/bcw2.pdf
#   make test     the tests of the tools
#   make clean    remove build/
#
# Sphinx runs tools/bcw.py on book/. It checks the book, reports each finding
# at its chapter line, and tangles the code into build/. Every location that
# make check prints is a line in the book: the output of Verilator and of each
# twin goes through tools/linemap.py.

SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -c
PY := .venv/bin/python
MAP := $(PY) tools/linemap.py
# -E reads every chapter, because Sphinx does not report again on a chapter
# that it read in an earlier build. sed shortens the paths that docutils prints.
SPHINX := $(PY) -m sphinx -E -q -b dummy -c tools book build/sphinx
RELATIVE := sed "s|$(CURDIR)/||"

.PHONY: tangle check weave test clean

tangle:
	$(SPHINX) 2>&1 | $(RELATIVE)

check:
	$(SPHINX) -W --keep-going 2>&1 | $(RELATIVE)
	@for f in $$(find build/rtl -name '*.v' | sort); do \
	    verilator --lint-only -Wall "$$f" 2>&1 | $(MAP) || exit 1; \
	done
	@for f in $$(find build/model -name '*.py' | sort); do \
	    $(PY) -c 'import runpy, sys; runpy.run_path(sys.argv[1])' "$$f" 2>&1 | $(MAP) || exit 1; \
	done

# The weave reports findings but does not stop on them: make check is the gate.
weave:
	$(PY) -m sphinx -E -q -b html -c tools book build/html 2>&1 | $(RELATIVE)
	LATEXMKOPTS=-quiet $(PY) -m sphinx -M latexpdf book build -E -q -c tools 2>&1 | $(RELATIVE)

test:
	$(PY) -m unittest discover -s tools/tests

clean:
	rm -rf build
