module alu_3_1 (input wire [31:0] a, b, output wire [31:0] y);
    core_alu u (.f3(3'd3), .alt(1'b1), .a, .b, .y);
endmodule
