module alu_2_1 (input wire [31:0] a, b, output wire [31:0] y);
    core_alu u (.f3(3'd2), .alt(1'b1), .a, .b, .y);
endmodule
