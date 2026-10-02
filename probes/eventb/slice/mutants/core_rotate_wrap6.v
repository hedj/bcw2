module core_rotate (input wire [bcw_params::CORE_TURN_WIDTH-1:0] turn,
                    output wire [bcw_params::CORE_TURN_WIDTH-1:0] next);
    assign next = (turn == bcw_params::CORE_TURN_WIDTH'(bcw_params::CORE_THREADS - 2)) ? '0 : turn + 1'b1;
endmodule
