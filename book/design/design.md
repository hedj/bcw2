# Design

## 1. Overview

This chapter states the goals of the design of the machine. A rule in another chapter names
the goal that it serves in its `parent=` list. The timing invariant comes from section 4.2 of
the BCW-2 workflow proposal, revision 12.

## 2. Goals

**GOAL.** No protection domain can alter the observed latency of an operation in any other
protection domain.
{rule=design.timing-invariant}
