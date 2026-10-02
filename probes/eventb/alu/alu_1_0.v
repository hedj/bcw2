module alu_1_0 (input wire [31:0] a, b, output wire [31:0] y);
    core_alu u (.f3(3'd1), .alt(1'b0), .a, .b, .y);
endmodule
