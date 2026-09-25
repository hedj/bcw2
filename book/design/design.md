# Design

## Overview

This chapter states the goals of the design of the machine. A rule in another chapter names
the goal that it serves in its `parent=` list. The timing invariant comes from section 4.2 of
the BCW-2 workflow proposal, revision 12.

## Goals

**GOAL.** No protection domain can alter the observed latency of an operation in any other
protection domain.
{rule=design.timing-invariant}

## Terms

**DEFINITION.** A **protection domain** is a set of threads and state that the machine keeps
apart from every other such set.
{rule=design.protection-domain parent=design.timing-invariant}

**DEFINITION.** An **operation** is an instruction or a request that a protection domain
issues.
{rule=design.operation parent=design.timing-invariant}

**DEFINITION.** The **observed latency** of an operation is the time from its issue to its
result, as its protection domain can measure that time.
{rule=design.observed-latency parent=design.timing-invariant}
