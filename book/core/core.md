# Core

## 1. Rotation

**REQUIREMENT.** Rotation shall be fixed and unconditional: the turn after
thread *t* belongs to thread *t* + 1, modulo the thread count.
{rule=core.rotation}

``` {.python .formal file=build/model/core_rotate.py stamp=099b2e9d}
def core_rotate(turn):
    return {'next': turn + 1}
```

``` {.verilog file=build/rtl/core/core_rotate.v implements=core.rotation}
module core_rotate (input wire [2:0] turn, output wire [2:0] next);
    assign next = turn + 3'd1;
endmodule
```
