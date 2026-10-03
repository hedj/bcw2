// The ECP5 block RAM in the one configuration that yosys's map of a 36-bit pseudo-dual-port
// memory ($__PDPW16KD_) gives: port A writes, port B reads, both 36 bits wide, no output register,
// no chip-select decode. Any other configuration stops elaboration. A word is {DIB, DIA} and
// {DOB, DOA}; ADA[13:5] and ADB[13:5] address one of 512 words; ADA[3:0] enable the four 9-bit
// bytes of a write. A read of the word that port A writes in the same cycle gives a free value
// ($anyseq): neither yosys's description of the block nor this model promises old or new data.
// The initial contents are ignored. Trusted, like the other cell models.
module DP16KD(
    input DIA0, DIA1, DIA2, DIA3, DIA4, DIA5, DIA6, DIA7, DIA8, DIA9, DIA10, DIA11, DIA12, DIA13, DIA14, DIA15, DIA16, DIA17, ADA0, ADA1, ADA2, ADA3, ADA4, ADA5, ADA6, ADA7, ADA8, ADA9, ADA10, ADA11, ADA12, ADA13, CEA, OCEA, CLKA, WEA, RSTA, CSA0, CSA1, CSA2, DIB0, DIB1, DIB2, DIB3, DIB4, DIB5, DIB6, DIB7, DIB8, DIB9, DIB10, DIB11, DIB12, DIB13, DIB14, DIB15, DIB16, DIB17, ADB0, ADB1, ADB2, ADB3, ADB4, ADB5, ADB6, ADB7, ADB8, ADB9, ADB10, ADB11, ADB12, ADB13, CEB, OCEB, CLKB, WEB, RSTB, CSB0, CSB1, CSB2,
    output DOA0, DOA1, DOA2, DOA3, DOA4, DOA5, DOA6, DOA7, DOA8, DOA9, DOA10, DOA11, DOA12, DOA13, DOA14, DOA15, DOA16, DOA17, DOB0, DOB1, DOB2, DOB3, DOB4, DOB5, DOB6, DOB7, DOB8, DOB9, DOB10, DOB11, DOB12, DOB13, DOB14, DOB15, DOB16, DOB17);
    parameter integer DATA_WIDTH_A = 18;
    parameter integer DATA_WIDTH_B = 18;
    parameter REGMODE_A = "NOREG";
    parameter REGMODE_B = "NOREG";
    parameter CSDECODE_A = "0b000";
    parameter CSDECODE_B = "0b000";
    parameter WRITEMODE_A = "NORMAL";
    parameter WRITEMODE_B = "NORMAL";
    parameter RESETMODE = "SYNC";
    parameter ASYNC_RESET_RELEASE = "SYNC";
    parameter CLKAMUX = "CLKA";
    parameter CLKBMUX = "CLKB";
    parameter GSR = "ENABLED";
    parameter INIT_DATA = "STATIC";
    parameter INITVAL_00 = 320'h0;
    parameter INITVAL_01 = 320'h0;
    parameter INITVAL_02 = 320'h0;
    parameter INITVAL_03 = 320'h0;
    parameter INITVAL_04 = 320'h0;
    parameter INITVAL_05 = 320'h0;
    parameter INITVAL_06 = 320'h0;
    parameter INITVAL_07 = 320'h0;
    parameter INITVAL_08 = 320'h0;
    parameter INITVAL_09 = 320'h0;
    parameter INITVAL_0A = 320'h0;
    parameter INITVAL_0B = 320'h0;
    parameter INITVAL_0C = 320'h0;
    parameter INITVAL_0D = 320'h0;
    parameter INITVAL_0E = 320'h0;
    parameter INITVAL_0F = 320'h0;
    parameter INITVAL_10 = 320'h0;
    parameter INITVAL_11 = 320'h0;
    parameter INITVAL_12 = 320'h0;
    parameter INITVAL_13 = 320'h0;
    parameter INITVAL_14 = 320'h0;
    parameter INITVAL_15 = 320'h0;
    parameter INITVAL_16 = 320'h0;
    parameter INITVAL_17 = 320'h0;
    parameter INITVAL_18 = 320'h0;
    parameter INITVAL_19 = 320'h0;
    parameter INITVAL_1A = 320'h0;
    parameter INITVAL_1B = 320'h0;
    parameter INITVAL_1C = 320'h0;
    parameter INITVAL_1D = 320'h0;
    parameter INITVAL_1E = 320'h0;
    parameter INITVAL_1F = 320'h0;
    parameter INITVAL_20 = 320'h0;
    parameter INITVAL_21 = 320'h0;
    parameter INITVAL_22 = 320'h0;
    parameter INITVAL_23 = 320'h0;
    parameter INITVAL_24 = 320'h0;
    parameter INITVAL_25 = 320'h0;
    parameter INITVAL_26 = 320'h0;
    parameter INITVAL_27 = 320'h0;
    parameter INITVAL_28 = 320'h0;
    parameter INITVAL_29 = 320'h0;
    parameter INITVAL_2A = 320'h0;
    parameter INITVAL_2B = 320'h0;
    parameter INITVAL_2C = 320'h0;
    parameter INITVAL_2D = 320'h0;
    parameter INITVAL_2E = 320'h0;
    parameter INITVAL_2F = 320'h0;
    parameter INITVAL_30 = 320'h0;
    parameter INITVAL_31 = 320'h0;
    parameter INITVAL_32 = 320'h0;
    parameter INITVAL_33 = 320'h0;
    parameter INITVAL_34 = 320'h0;
    parameter INITVAL_35 = 320'h0;
    parameter INITVAL_36 = 320'h0;
    parameter INITVAL_37 = 320'h0;
    parameter INITVAL_38 = 320'h0;
    parameter INITVAL_39 = 320'h0;
    parameter INITVAL_3A = 320'h0;
    parameter INITVAL_3B = 320'h0;
    parameter INITVAL_3C = 320'h0;
    parameter INITVAL_3D = 320'h0;
    parameter INITVAL_3E = 320'h0;
    parameter INITVAL_3F = 320'h0;
    generate
        if (DATA_WIDTH_A != 36 || DATA_WIDTH_B != 36 || REGMODE_A != "NOREG" || REGMODE_B != "NOREG"
            || CSDECODE_A != "0b000" || CSDECODE_B != "0b000" || CLKAMUX != "CLKA" || CLKBMUX != "CLKB")
            ERROR_UNMODELLED_DP16KD_MODE error();
    endgenerate
    reg [35:0] mem [0:511];
    reg [35:0] q;
    (* anyseq *) wire [35:0] collision;
    wire [35:0] wd = {DIB17, DIB16, DIB15, DIB14, DIB13, DIB12, DIB11, DIB10, DIB9, DIB8, DIB7, DIB6, DIB5, DIB4, DIB3, DIB2, DIB1, DIB0, DIA17, DIA16, DIA15, DIA14, DIA13, DIA12, DIA11, DIA10, DIA9, DIA8, DIA7, DIA6, DIA5, DIA4, DIA3, DIA2, DIA1, DIA0};
    wire [8:0] wa = {ADA13, ADA12, ADA11, ADA10, ADA9, ADA8, ADA7, ADA6, ADA5};
    wire [3:0] be = {ADA3, ADA2, ADA1, ADA0};
    wire [8:0] ra = {ADB13, ADB12, ADB11, ADB10, ADB9, ADB8, ADB7, ADB6, ADB5};
    wire write = CEA && WEA && {CSA2, CSA1, CSA0} == 3'b000;
    wire read = CEB && {CSB2, CSB1, CSB0} == 3'b000;
    integer k;
    always @(posedge CLKA)
        if (write)
            for (k = 0; k < 4; k = k + 1)
                if (be[k]) mem[wa][9 * k +: 9] <= wd[9 * k +: 9];
    always @(posedge CLKB)
        if (RSTB) q <= 36'd0;
        else if (read) q <= write && wa == ra && |be ? collision : mem[ra];
    assign {DOB17, DOB16, DOB15, DOB14, DOB13, DOB12, DOB11, DOB10, DOB9, DOB8, DOB7, DOB6, DOB5, DOB4, DOB3, DOB2, DOB1, DOB0, DOA17, DOA16, DOA15, DOA14, DOA13, DOA12, DOA11, DOA10, DOA9, DOA8, DOA7, DOA6, DOA5, DOA4, DOA3, DOA2, DOA1, DOA0} = q;
endmodule
