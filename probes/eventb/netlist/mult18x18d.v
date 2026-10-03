// The 18x18 multiplier of the ECP5 DSP block, in its combinational configuration only: no input,
// pipeline or output register, and no bypass; any other configuration stops elaboration. P is
// the 36-bit product of A and B, each signed when SIGNEDA or SIGNEDB is 1; SOURCEA and SOURCEB
// take A and B from the cascade inputs SRIA and SRIB. Only P is driven: a design that used another
// output would leave it undriven, and its proof would fail. Trusted, like the other cell models.
module MULT18X18D(
    input A0, A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, A11, A12, A13, A14, A15, A16, A17, B0, B1, B2, B3, B4, B5, B6, B7, B8, B9, B10, B11, B12, B13, B14, B15, B16, B17, C0, C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C12, C13, C14, C15, C16, C17, SIGNEDA, SIGNEDB, SOURCEA, SOURCEB, CLK0, CLK1, CLK2, CLK3, CE0, CE1, CE2, CE3, RST0, RST1, RST2, RST3, SRIA0, SRIA1, SRIA2, SRIA3, SRIA4, SRIA5, SRIA6, SRIA7, SRIA8, SRIA9, SRIA10, SRIA11, SRIA12, SRIA13, SRIA14, SRIA15, SRIA16, SRIA17, SRIB0, SRIB1, SRIB2, SRIB3, SRIB4, SRIB5, SRIB6, SRIB7, SRIB8, SRIB9, SRIB10, SRIB11, SRIB12, SRIB13, SRIB14, SRIB15, SRIB16, SRIB17,
    output SROA0, SROA1, SROA2, SROA3, SROA4, SROA5, SROA6, SROA7, SROA8, SROA9, SROA10, SROA11, SROA12, SROA13, SROA14, SROA15, SROA16, SROA17, SROB0, SROB1, SROB2, SROB3, SROB4, SROB5, SROB6, SROB7, SROB8, SROB9, SROB10, SROB11, SROB12, SROB13, SROB14, SROB15, SROB16, SROB17, ROA0, ROA1, ROA2, ROA3, ROA4, ROA5, ROA6, ROA7, ROA8, ROA9, ROA10, ROA11, ROA12, ROA13, ROA14, ROA15, ROA16, ROA17, ROB0, ROB1, ROB2, ROB3, ROB4, ROB5, ROB6, ROB7, ROB8, ROB9, ROB10, ROB11, ROB12, ROB13, ROB14, ROB15, ROB16, ROB17, ROC0, ROC1, ROC2, ROC3, ROC4, ROC5, ROC6, ROC7, ROC8, ROC9, ROC10, ROC11, ROC12, ROC13, ROC14, ROC15, ROC16, ROC17, P0, P1, P2, P3, P4, P5, P6, P7, P8, P9, P10, P11, P12, P13, P14, P15, P16, P17, P18, P19, P20, P21, P22, P23, P24, P25, P26, P27, P28, P29, P30, P31, P32, P33, P34, P35, SIGNEDP);
    parameter REG_INPUTA_CLK = "NONE";
    parameter REG_INPUTB_CLK = "NONE";
    parameter REG_INPUTC_CLK = "NONE";
    parameter REG_PIPELINE_CLK = "NONE";
    parameter REG_OUTPUT_CLK = "NONE";
    parameter MULT_BYPASS = "DISABLED";
    generate
        if (REG_INPUTA_CLK != "NONE" || REG_INPUTB_CLK != "NONE" || REG_INPUTC_CLK != "NONE" || REG_PIPELINE_CLK != "NONE" || REG_OUTPUT_CLK != "NONE" || MULT_BYPASS != "DISABLED")
            ERROR_UNMODELLED_MULT18X18D_MODE error();
    endgenerate
    wire [17:0] a = SOURCEA ? {SRIA17, SRIA16, SRIA15, SRIA14, SRIA13, SRIA12, SRIA11, SRIA10, SRIA9, SRIA8, SRIA7, SRIA6, SRIA5, SRIA4, SRIA3, SRIA2, SRIA1, SRIA0} : {A17, A16, A15, A14, A13, A12, A11, A10, A9, A8, A7, A6, A5, A4, A3, A2, A1, A0};
    wire [17:0] b = SOURCEB ? {SRIB17, SRIB16, SRIB15, SRIB14, SRIB13, SRIB12, SRIB11, SRIB10, SRIB9, SRIB8, SRIB7, SRIB6, SRIB5, SRIB4, SRIB3, SRIB2, SRIB1, SRIB0} : {B17, B16, B15, B14, B13, B12, B11, B10, B9, B8, B7, B6, B5, B4, B3, B2, B1, B0};
    // One product for each signedness, so that with SIGNEDA and SIGNEDB constant the model is a
    // single 18x18 multiply of the form the RTL's own multiply takes.
    wire [35:0] uu = a * b;
    wire [35:0] us = $signed({1'b0, a}) * $signed(b);
    wire [35:0] su = $signed(a) * $signed({1'b0, b});
    wire [35:0] ss = $signed(a) * $signed(b);
    assign {P35, P34, P33, P32, P31, P30, P29, P28, P27, P26, P25, P24, P23, P22, P21, P20, P19, P18, P17, P16, P15, P14, P13, P12, P11, P10, P9, P8, P7, P6, P5, P4, P3, P2, P1, P0} = SIGNEDA ? (SIGNEDB ? ss : su) : (SIGNEDB ? us : uu);
endmodule
