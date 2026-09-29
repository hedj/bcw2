#!/usr/bin/env python3
"""yosys-smtbmc, which checks the steps of a bounded run 4 at a time.

tools/run_checks.py gives it to SymbiYosys for the mutants of a prove, which
pass when an assertion fails. SymbiYosys runs smtbmc with -t <depth>, which
checks one step in each query, so each query first proves the earlier steps
clean. -t 0:4:<depth> asks in one query whether an assertion fails in any of 4
steps. Every step is still checked, and a failure is still a trace.
"""
import os
import sys

args = sys.argv[1:]
depth = args.index("-t") + 1
if args[depth].isdigit():
    args[depth] = f"0:4:{args[depth]}"
os.execvp("yosys-smtbmc", ["yosys-smtbmc", *args])
