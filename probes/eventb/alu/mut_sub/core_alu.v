module core_alu (input wire [2:0] f3, input wire alt, input wire [31:0] a, b,
                 output reg [31:0] y);
    always @* case (f3)
        3'd0: y = alt ? b - a : a + b;
        3'd1: y = a << b[4:0];
        3'd2: y = {31'd0, $signed(a) < $signed(b)};
        3'd3: y = {31'd0, a < b};
        3'd4: y = a ^ b;
        3'd5: y = alt ? $unsigned($signed(a) >>> b[4:0]) : a >> b[4:0];
        3'd6: y = a | b;
        default: y = a & b;
    endcase
endmodule
