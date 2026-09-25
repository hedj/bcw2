# Core

## 1. Overview

The core runs every thread of the machine through one pipeline. The threads take turns in a
fixed order, so no thread can change when another thread gets its turn.

## 2. Rotation

**DEFINITION.** The **core** is the part of the machine that issues the instructions of every
thread.
{rule=core.core parent=design.timing-invariant}

**REQUIREMENT.** The core shall give the turn after thread *t* to thread *t* + 1, modulo the
thread count.
{rule=core.rotation parent=design.timing-invariant}

``` {.python .formal file=build/model/core_rotate.py stamp=1a7d6146}
def core_rotate(turn):
    return {'next': turn + 1}
```

``` {.verilog file=build/rtl/core/core_rotate.v implements=core.rotation}
module core_rotate (input wire [2:0] turn, output wire [2:0] next);
    assign next = turn + 3'd1;
endmodule
```

**RATIONALE.** The order of the turns depends on nothing that a thread does. No thread can
therefore change the timing of another thread, as `design.timing-invariant` requires.
