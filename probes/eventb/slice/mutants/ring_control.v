// The ring of core.v, reduced to its structure: the turn register, and one record for each thread
// that travels the 8 stages. Only W changes a record, by one step of its thread: here after = w + in.
module ring (input wire clk, rst_n, input wire [7:0] in, output wire [2:0] turn, output wire [7:0] w);
    logic [2:0] rot, rot_next;
    core_rotate rotate (.turn(rot), .next(rot_next));
    assign turn = rot;
    logic [7:0] f_rec, x_rec, d_rec, r_rec, e_rec, m1_rec, m2_rec, w_rec;
    wire [7:0] after = w_rec + in;
    assign w = w_rec;
    always_ff @(posedge clk) begin
        rot <= rst_n ? rot + 3'd1 : '0;
        {f_rec, x_rec, d_rec, r_rec, e_rec, m1_rec, m2_rec, w_rec}
            <= rst_n ? {after, f_rec, x_rec, d_rec, r_rec, e_rec, m1_rec, m2_rec} : {8'd1, {7{8'd0}}};
    end
endmodule
