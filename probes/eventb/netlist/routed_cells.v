// Models of the cells of nextpnr-ecp5's routed netlist that yosys's ECP5 library lacks or models
// otherwise. They are trusted, like cells_sim.v.

// The flip-flop as nextpnr packs it: SD selects the data, 0 the direct input M, 1 the LUT output DI
// (Trellis REGx_SD). Clock enable, clock and reset polarity as in yosys's TRELLIS_FF.
module TRELLIS_FF(input CLK, LSR, CE, DI, M, output reg Q);
    parameter GSR = "ENABLED";
    parameter [127:0] CEMUX = "1";
    parameter CLKMUX = "CLK";
    parameter LSRMUX = "LSR";
    parameter SRMODE = "LSR_OVER_CE";
    parameter REGSET = "RESET";
    parameter [127:0] SD = "1";
    wire muxce = (CEMUX == "1") ? 1'b1 : (CEMUX == "0") ? 1'b0 : (CEMUX == "INV") ? ~CE : CE;
    wire srval = (REGSET == "SET") ? 1'b1 : 1'b0;
    wire data = (SD == "0") ? M : DI;
    initial Q = srval;
    generate
        if (CLKMUX != "CLK" || LSRMUX != "LSR" || SRMODE != "LSR_OVER_CE")
            ERROR_UNMODELLED_TRELLIS_FF_MODE error();
    endgenerate
    always @(posedge CLK)
        if (LSR) Q <= srval;
        else if (muxce) Q <= data;
endmodule

// The I/O buffer with its tristate control unconnected: an input passes the pad, an output drives it.
module TRELLIS_IO(inout B, input I, T, IOLDO, IOLTO, output O);
    parameter DIR = "INPUT";
    parameter DATAMUX_MDDR = "PADDO";   // the pad's data from I, not from an I/O register
    parameter DATAMUX_ODDR = "PADDO";
    generate
        if (DATAMUX_MDDR != "PADDO" || DATAMUX_ODDR != "PADDO") ERROR_UNMODELLED_IO_DATAMUX error();
        if (DIR == "INPUT") assign O = B;
        else if (DIR == "OUTPUT") assign B = I;
        else ERROR_UNMODELLED_IO_MODE error();
    endgenerate
endmodule

// The global clock buffer with its enable unconnected.
module DCCA(input CLKI, CE, output CLKO);
    assign CLKO = CLKI;
endmodule

// yosys's TRELLIS_COMB (common_sim.vh, yosys 0.69) declares "wire FCO = ..." inside the CCU2
// generate block, a new local wire, so its output port FCO is undriven and the carry chain is
// lost. This copy assigns the port. Only the modes LOGIC and CCU2 are modelled.
module TRELLIS_COMB(
    input A, B, C, D, M,
    input FCI, F1, FXA, FXB,
    input WD,
    input WAD0, WAD1, WAD2, WAD3,
    input WRE, WCK,
    output F, FCO, OFX
);
    parameter MODE = "LOGIC";
    parameter INITVAL = 16'h0;
    parameter CCU2_INJECT1 = "NO";
    parameter WREMUX = "WRE";
    parameter IS_Z1 = 1'b0;
    generate
        if (MODE == "LOGIC") begin: mode_logic
            LUT4 #(.INIT(INITVAL)) lut4 (.A(A), .B(B), .C(C), .D(D), .Z(F));
        end else if (MODE == "CCU2") begin: mode_ccu2
            wire l4o, l2o;
            LUT4 #(.INIT(INITVAL)) lut4_0(.A(A), .B(B), .C(C), .D(D), .Z(l4o));
            LUT2 #(.INIT(INITVAL[3:0])) lut2_0(.A(A), .B(B), .Z(l2o));
            wire gated_cin_0 = (CCU2_INJECT1 == "YES") ? 1'b0 : FCI;
            assign F = l4o ^ gated_cin_0;
            wire gated_lut2_0 = (CCU2_INJECT1 == "YES") ? 1'b0 : l2o;
            assign FCO = (~l4o & gated_lut2_0) | (l4o & FCI);
        end else begin
            ERROR_UNMODELLED_COMB_MODE error();
        end
        if (IS_Z1)
            L6MUX21 lutx_mux (.D0(FXA), .D1(FXB), .SD(M), .Z(OFX));
        else
            PFUMX lut5_mux (.ALUT(F1), .BLUT(F), .C0(M), .Z(OFX));
    endgenerate
endmodule
