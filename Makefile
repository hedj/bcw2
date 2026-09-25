# Run from the repository root, after sh tools/setup.sh.
#
#   make tangle   tangle the book into build/
#   make check    the fast checks, Verilator lint and a load of each twin
#   make test     the tests of the tools
#   make clean    remove build/ and entangled's database
#
# Every location that make check prints is a line in the book: the output of
# each tool goes through tools/linemap.py.

SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -c
PY := .venv/bin/python
MAP := $(PY) tools/linemap.py

.PHONY: tangle check test clean

tangle:
	$(PY) tools/tangle.py

check: tangle
	$(PY) tools/check.py
	@for f in $$(find build/rtl -name '*.v' | sort); do \
	    verilator --lint-only -Wall "$$f" 2>&1 | $(MAP) || exit 1; \
	done
	@for f in $$(find build/model -name '*.py' | sort); do \
	    $(PY) -c 'import runpy, sys; runpy.run_path(sys.argv[1])' "$$f" 2>&1 | $(MAP) || exit 1; \
	done

test:
	$(PY) -m unittest discover -s tools/tests

clean:
	rm -rf build .entangled
