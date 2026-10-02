// The carries of $lcu as a ripple chain, in place of yosys's Brent-Kung tree: CO[i] = G[i] | P[i] & CO[i-1].
(* techmap_celltype = "$lcu" *)
module _80_lcu_ripple (P, G, CI, CO);
	parameter WIDTH = 2;
	input [WIDTH-1:0] P, G;
	input CI;
	output [WIDTH-1:0] CO;
	genvar i;
	generate for (i = 0; i < WIDTH; i = i + 1) begin: chain
		if (i == 0) assign CO[0] = G[0] | P[0] & CI;
		else assign CO[i] = G[i] | P[i] & CO[i-1];
	end endgenerate
endmodule
