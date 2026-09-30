:kind: reference

====
Core
====

Overview
========

The core runs every thread of the machine through one pipeline. The threads take turns in a
fixed order, so no thread can change when another thread has its turn.

Rotation
========

.. definition:: core.core
   :parent: design.timing-invariant

   The :dfn:`core` is the part of the machine that issues the instructions of every thread.

.. definition:: core.thread
   :parent: core.core

   A :dfn:`thread` is a stream of instructions with its own registers and program counter.

.. definition:: core.turn
   :parent: core.core

   A :dfn:`turn` is a cycle in which the core issues an instruction of one thread.

.. parameter:: core.threads
   :parent: core.core
   :value: 8

   The number of threads that the core runs.

.. parameter:: core.turn-width
   :parent: core.threads
   :value: clog2(core.threads)
   :unit: bits

   The width of the number of a thread.

.. parameter:: core.clock
   :parent: core.core
   :value: 85 * 10 ** 6
   :unit: Hz

   The number of cycles in a second.

.. target:: core.timing-closure
   :parent: core.clock
   :value: core.clock
   :unit: Hz

   The core satisfies timing closure at :param:`core.clock`.

.. requirement:: core.rotation
   :parent: design.timing-invariant

   The core shall give the turn after thread ``t`` to thread ``t + 1``, modulo
   :param:`core.threads`.

   .. twin::
      :stamp: 75abc2dc

      def core_rotate(turn):
          return {'next': (turn + 1) % CORE_THREADS}

.. source:: build/rtl/core/core_rotate.v
   :implements: core.rotation

   module core_rotate (input wire [bcw_params::CORE_TURN_WIDTH-1:0] turn,
                       output wire [bcw_params::CORE_TURN_WIDTH-1:0] next);
       assign next = (turn == bcw_params::CORE_TURN_WIDTH'(bcw_params::CORE_THREADS - 1)) ? '0 : turn + 1'b1;
   endmodule

.. check:: equiv
   :verifies: core.rotation
   :module: core_rotate

.. rationale::

   The order of the turns depends on nothing that a thread does. No thread can therefore
   change the timing of another thread, as :rule:`design.timing-invariant` requires.

Instruction set
===============

.. definition:: core.compressed
   :parent: design.economy

   A :dfn:`compressed instruction` is a 16-bit instruction of the ``C`` extension of ``RISC-V``
   for ``RV32``. One that the extension reserves, or that needs an extension other than ``I``,
   ``M`` and ``C``, is illegal, and expands to ``0x00000013``.

.. requirement:: core.rvc0
   :parent: design.economy

   Where a compressed instruction has ``00`` in its lowest two bits, the core shall
   expand it as the ``C`` extension defines.

   .. twin::
      :stamp: de7eb8be

      def enc_i(imm, rs1, f3, rd, op):
          return ((imm & 4095) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op
      def enc_s(imm, rs2, rs1, f3):
          low = ((imm >> 5) & 127) << 25
          return low | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | ((imm & 31) << 7) | 35
      def core_rvc0(c):
          f3 = (c >> 13) & 7
          rdp = 8 + ((c >> 2) & 7)
          r1p = 8 + ((c >> 7) & 7)
          spn = ((((c >> 11) & 3) << 4) | (((c >> 7) & 15) << 6)
                 | (((c >> 6) & 1) << 2) | (((c >> 5) & 1) << 3))
          word = ((((c >> 10) & 7) << 3) | (((c >> 6) & 1) << 2)
                  | (((c >> 5) & 1) << 6))
          addi4spn = -1 if spn == 0 else enc_i(spn, 2, 0, rdp, 19)
          code = (addi4spn if f3 == 0 else enc_i(word, r1p, 2, rdp, 3) if f3 == 2
                  else enc_s(word, rdp, r1p, 2) if f3 == 6 else -1)
          bad = code < 0 or (c & 3) != 0
          return {'insn': 19 if bad else code, 'illegal': 1 if bad else 0}

.. source:: build/rtl/core/core_rvc0.v
   :implements: core.rvc0

   module core_rvc0 (input wire [15:0] c, output reg [31:0] insn, output reg illegal);
       localparam OP_IMM = 7'b0010011, OP_LOAD = 7'b0000011, OP_STORE = 7'b0100011;
       wire [4:0]  rdp          = {2'b01, c[4:2]};
       wire [4:0]  r1p          = {2'b01, c[9:7]};
       wire [11:0] imm_addi4spn = {2'b0, c[10:7], c[12:11], c[5], c[6], 2'b0};
       wire [11:0] imm_lwsw     = {5'b0, c[5], c[12:10], c[6], 2'b0};
       always @* begin
           insn    = 32'h00000013;
           illegal = 1'b0;
           if (c[1:0] != 2'b00) illegal = 1'b1;
           else case (c[15:13])
               3'b000: if (c[12:5] == 8'b0) illegal = 1'b1;                         // reserved
                       else insn = rv32::enc_i(imm_addi4spn, 5'd2, 3'b000, rdp, OP_IMM);
               3'b010: insn = rv32::enc_i(imm_lwsw, r1p, 3'b010, rdp, OP_LOAD);    // c.lw
               3'b110: insn = rv32::enc_s(imm_lwsw, rdp, r1p, 3'b010, OP_STORE);   // c.sw
               default: illegal = 1'b1;                                           // F, D, reserved
           endcase
           if (illegal) insn = 32'h00000013;
       end
   endmodule

.. check:: equiv
   :verifies: core.rvc0
   :module: core_rvc0

.. requirement:: core.rvc1
   :parent: design.economy

   Where a compressed instruction has ``01`` in its lowest two bits, the core shall
   expand it as the ``C`` extension defines.

   .. twin::
      :stamp: d1d13581

      def enc_i(imm, rs1, f3, rd, op):
          return ((imm & 4095) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op
      def enc_r(f7, rs2, rs1, f3, rd, op):
          return (f7 << 25) | (rs2 << 20) | enc_i(0, rs1, f3, rd, op)
      def enc_b(imm, rs1, f3):
          high = (((imm >> 12) & 1) << 6) | ((imm >> 5) & 63)
          low = (((imm >> 1) & 15) << 1) | ((imm >> 11) & 1)
          return enc_r(high, 0, rs1, f3, low, 99)
      def enc_j(imm, rd):
          high = (((imm >> 20) & 1) << 19) | (((imm >> 1) & 1023) << 9)
          field = high | (((imm >> 11) & 1) << 8) | ((imm >> 12) & 255)
          return (field << 12) | (rd << 7) | 111
      def core_rvc1(c):
          f3 = (c >> 13) & 7
          b12 = (c >> 12) & 1
          rd = (c >> 7) & 31
          rdp = 8 + ((c >> 2) & 7)
          r1p = 8 + ((c >> 7) & 7)
          six = (b12 << 5) | ((c >> 2) & 31)
          imm = six - 64 * b12
          jump = ((b12 << 11) | (((c >> 11) & 1) << 4) | (((c >> 9) & 3) << 8)
                  | (((c >> 8) & 1) << 10) | (((c >> 7) & 1) << 6)
                  | (((c >> 6) & 1) << 7) | (((c >> 3) & 7) << 1)
                  | (((c >> 2) & 1) << 5)) - 4096 * b12
          sp16 = ((b12 << 9) | (((c >> 6) & 1) << 4) | (((c >> 5) & 1) << 6)
                  | (((c >> 3) & 3) << 7) | (((c >> 2) & 1) << 5))
          branch = ((b12 << 8) | (((c >> 10) & 3) << 3) | (((c >> 5) & 3) << 6)
                    | (((c >> 3) & 3) << 1) | (((c >> 2) & 1) << 5)) - 512 * b12
          addi16sp = -1 if sp16 == 0 else enc_i(sp16 - 1024 * b12, 2, 0, 2, 19)
          lui = -1 if six == 0 else ((imm & 1048575) << 12) | (rd << 7) | 55
          funct2 = (c >> 10) & 3
          funct = (c >> 5) & 3
          arith_f3 = 0 if funct == 0 else 4 if funct == 1 else 4 + funct
          arith = enc_r(32 if funct == 0 else 0, rdp, r1p, arith_f3, r1p, 51)
          shamt = (1024 if funct2 == 1 else 0) | ((c >> 2) & 31)
          shift = enc_i(shamt, r1p, 5, r1p, 19)
          alu = (enc_i(imm, r1p, 7, r1p, 19) if funct2 == 2 else -1 if b12 == 1
                 else shift if funct2 < 2 else arith)
          code = (enc_i(imm, rd, 0, rd, 19) if f3 == 0 else enc_j(jump, 1) if f3 == 1
                  else enc_i(imm, 0, 0, rd, 19) if f3 == 2
                  else (addi16sp if rd == 2 else lui) if f3 == 3 else alu if f3 == 4
                  else enc_j(jump, 0) if f3 == 5 else enc_b(branch, r1p, f3 - 6))
          bad = code < 0 or (c & 3) != 1
          return {'insn': 19 if bad else code, 'illegal': 1 if bad else 0}

.. source:: build/rtl/core/core_rvc1.v
   :implements: core.rvc1

   module core_rvc1 (input wire [15:0] c, output reg [31:0] insn, output reg illegal);
       localparam OP_IMM = 7'b0010011, OP_REG = 7'b0110011, OP_LUI = 7'b0110111,
                  OP_JAL = 7'b1101111, OP_BR = 7'b1100011;
       wire [4:0]  rd_full      = c[11:7];
       wire [4:0]  r1p          = {2'b01, c[9:7]};
       wire [4:0]  rdp          = {2'b01, c[4:2]};
       wire [11:0] imm_ci       = {{7{c[12]}}, c[6:2]};
       wire [11:0] imm_addi16sp = {{3{c[12]}}, c[4:3], c[5], c[2], c[6], 4'b0};
       wire [5:0]  shamt        = {c[12], c[6:2]};
       wire [20:1] imm_cj = {{10{c[12]}}, c[8], c[10:9], c[6], c[7], c[2], c[11], c[5:3]};
       wire [12:1] imm_cb = {{5{c[12]}}, c[6:5], c[2], c[11:10], c[4:3]};
       always @* begin
           insn    = 32'h00000013;
           illegal = 1'b0;
           if (c[1:0] != 2'b01) illegal = 1'b1;
           else case (c[15:13])
               3'b000: insn = rv32::enc_i(imm_ci, rd_full, 3'b000, rd_full, OP_IMM);      // c.addi
               3'b001: insn = rv32::enc_j(imm_cj, 5'd1, OP_JAL);                          // c.jal
               3'b010: insn = rv32::enc_i(imm_ci, 5'd0, 3'b000, rd_full, OP_IMM);         // c.li
               3'b011: if ({c[12], c[6:2]} == 6'b0) illegal = 1'b1;                       // reserved
                       else if (rd_full == 5'd2)                                          // c.addi16sp
                           insn = rv32::enc_i(imm_addi16sp, 5'd2, 3'b000, 5'd2, OP_IMM);
                       else insn = {{15{c[12]}}, c[6:2], rd_full, OP_LUI};                // c.lui
               3'b100: case (c[11:10])
                   2'b00: if (c[12]) illegal = 1'b1;                                      // c.srli
                          else insn = rv32::enc_i({6'b0, shamt}, r1p, 3'b101, r1p, OP_IMM);
                   2'b01: if (c[12]) illegal = 1'b1;                                      // c.srai
                          else insn = rv32::enc_i({6'b010000, shamt}, r1p, 3'b101, r1p, OP_IMM);
                   2'b10: insn = rv32::enc_i(imm_ci, r1p, 3'b111, r1p, OP_IMM);           // c.andi
                   2'b11: if (c[12]) illegal = 1'b1;                                      // RV64 only
                          else case (c[6:5])
                       2'b00: insn = rv32::enc_r(7'b0100000, rdp, r1p, 3'b000, r1p, OP_REG);  // sub
                       2'b01: insn = rv32::enc_r(7'b0000000, rdp, r1p, 3'b100, r1p, OP_REG);  // xor
                       2'b10: insn = rv32::enc_r(7'b0000000, rdp, r1p, 3'b110, r1p, OP_REG);  // or
                       2'b11: insn = rv32::enc_r(7'b0000000, rdp, r1p, 3'b111, r1p, OP_REG);  // and
                   endcase
               endcase
               3'b101: insn = rv32::enc_j(imm_cj, 5'd0, OP_JAL);                          // c.j
               3'b110: insn = rv32::enc_b(imm_cb, 5'd0, r1p, 3'b000, OP_BR);              // c.beqz
               3'b111: insn = rv32::enc_b(imm_cb, 5'd0, r1p, 3'b001, OP_BR);              // c.bnez
           endcase
           if (illegal) insn = 32'h00000013;
       end
   endmodule

.. check:: equiv
   :verifies: core.rvc1
   :module: core_rvc1

.. requirement:: core.rvc2
   :parent: design.economy

   Where a compressed instruction has ``10`` in its lowest two bits, the core shall
   expand it as the ``C`` extension defines.

   .. twin::
      :stamp: 5038c648

      def enc_i(imm, rs1, f3, rd, op):
          return ((imm & 4095) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op
      def enc_r(rs2, rs1, rd):
          return (rs2 << 20) | enc_i(0, rs1, 0, rd, 51)
      def core_rvc2(c):
          f3 = (c >> 13) & 7
          b12 = (c >> 12) & 1
          rd = (c >> 7) & 31
          rs2 = (c >> 2) & 31
          lwsp = (b12 << 5) | (((c >> 4) & 7) << 2) | (((c >> 2) & 3) << 6)
          swsp = (((c >> 9) & 15) << 2) | (((c >> 7) & 3) << 6)
          store = (((swsp >> 5) & 127) << 25) | (rs2 << 20) | (2 << 15) | (2 << 12)
          jr = -1 if rd == 0 else enc_i(0, rd, 0, 0, 103)
          low = jr if rs2 == 0 else enc_r(rs2, 0, rd)
          high = ((1048691 if rd == 0 else enc_i(0, rd, 0, 1, 103)) if rs2 == 0 else
                  enc_r(rs2, rd, rd))
          code = ((-1 if b12 == 1 else enc_i(rs2, rd, 1, rd, 19)) if f3 == 0 else
                  (-1 if rd == 0 else enc_i(lwsp, 2, 2, rd, 3)) if f3 == 2 else
                  (high if b12 == 1 else low) if f3 == 4 else
                  store | ((swsp & 31) << 7) | 35 if f3 == 6 else -1)
          bad = code < 0 or (c & 3) != 2
          return {'insn': 19 if bad else code, 'illegal': 1 if bad else 0}

.. source:: build/rtl/core/core_rvc2.v
   :implements: core.rvc2

   module core_rvc2 (input wire [15:0] c, output reg [31:0] insn, output reg illegal);
       localparam OP_IMM = 7'b0010011, OP_REG = 7'b0110011, OP_LOAD = 7'b0000011,
                  OP_STORE = 7'b0100011, OP_JALR = 7'b1100111;
       wire [4:0]  rd_full  = c[11:7];
       wire [4:0]  rs2_full = c[6:2];
       wire [5:0]  shamt    = {c[12], c[6:2]};
       wire [11:0] imm_lwsp = {4'b0, c[3:2], c[12], c[6:4], 2'b0};
       wire [11:0] imm_swsp = {4'b0, c[8:7], c[12:9], 2'b0};
       always @* begin
           insn    = 32'h00000013;
           illegal = 1'b0;
           if (c[1:0] != 2'b10) illegal = 1'b1;
           else case (c[15:13])
               3'b000: if (c[12]) illegal = 1'b1;                                         // RV32: shamt[5]
                       else insn = rv32::enc_i({6'b0, shamt}, rd_full, 3'b001, rd_full, OP_IMM);
               3'b010: if (rd_full == 5'd0) illegal = 1'b1;                               // c.lwsp
                       else insn = rv32::enc_i(imm_lwsp, 5'd2, 3'b010, rd_full, OP_LOAD);
               3'b100: if (!c[12] && rs2_full == 5'd0 && rd_full == 5'd0)
                           illegal = 1'b1;                                                // reserved
                       else if (!c[12] && rs2_full == 5'd0)                               // c.jr
                           insn = rv32::enc_i(12'b0, rd_full, 3'b000, 5'd0, OP_JALR);
                       else if (!c[12])                                                   // c.mv
                           insn = rv32::enc_r(7'b0, rs2_full, 5'd0, 3'b000, rd_full, OP_REG);
                       else if (rs2_full == 5'd0 && rd_full == 5'd0)
                           insn = 32'h00100073;                                           // c.ebreak
                       else if (rs2_full == 5'd0)                                         // c.jalr
                           insn = rv32::enc_i(12'b0, rd_full, 3'b000, 5'd1, OP_JALR);
                       else insn = rv32::enc_r(7'b0, rs2_full, rd_full, 3'b000, rd_full, OP_REG); // c.add
               3'b110: insn = rv32::enc_s(imm_swsp, rs2_full, 5'd2, 3'b010, OP_STORE);    // c.swsp
               default: illegal = 1'b1;                                                   // F, D
           endcase
           if (illegal) insn = 32'h00000013;
       end
   endmodule

.. check:: equiv
   :verifies: core.rvc2
   :module: core_rvc2

.. source:: build/rtl/core/rv32.sv

   // The encoders of the formats of RV32, which the expanders and the test of the core call.
   package rv32;
       function [31:0] enc_i(input [11:0] imm_f, input [4:0] rs1_f,
                             input [2:0] fn3, input [4:0] rd_f, input [6:0] op_f);
           enc_i = {imm_f, rs1_f, fn3, rd_f, op_f};
       endfunction
       function [31:0] enc_s(input [11:0] imm_f, input [4:0] rs2_f, input [4:0] rs1_f,
                             input [2:0] fn3, input [6:0] op_f);
           enc_s = {imm_f[11:5], rs2_f, rs1_f, fn3, imm_f[4:0], op_f};
       endfunction
       function [31:0] enc_r(input [6:0] f7_f, input [4:0] rs2_f, input [4:0] rs1_f,
                             input [2:0] fn3, input [4:0] rd_f, input [6:0] op_f);
           enc_r = {f7_f, rs2_f, rs1_f, fn3, rd_f, op_f};
       endfunction
       function [31:0] enc_b(input [12:1] imm_f, input [4:0] rs2_f, input [4:0] rs1_f,
                             input [2:0] fn3, input [6:0] op_f);
           enc_b = {imm_f[12], imm_f[10:5], rs2_f, rs1_f, fn3, imm_f[4:1], imm_f[11], op_f};
       endfunction
       function [31:0] enc_j(input [20:1] imm_f, input [4:0] rd_f, input [6:0] op_f);
           enc_j = {imm_f[20], imm_f[10:1], imm_f[11], imm_f[19:12], rd_f, op_f};
       endfunction
   endpackage

.. rationale::

   A stock instruction set adds no concept and brings a toolchain that works. The ``C``
   extension makes code smaller, which eases the pressure on the memory pool.

Decode
======

.. requirement:: core.decode
   :parent: design.economy, design.no-clock

   The core shall decode each instruction as the class that ``RV32IM`` gives it, or as an
   illegal instruction where ``RV32IM`` gives it no class.

   .. twin::
      :stamp: 0ac485f6

      def core_decode(insn):
          code = insn & 127
          f3 = (insn >> 12) & 7
          f7 = insn >> 25
          shift = f3 == 1 or f3 == 5
          base = f7 == 0 or (f7 == 32 and (f3 == 0 or f3 == 5))
          imm = code == 19 and (not shift or f7 == 0 or (f3 == 5 and f7 == 32))
          reg = code == 51 and base
          muldiv = code == 51 and f7 == 1
          lui = code == 55
          auipc = code == 23
          jal = code == 111
          jalr = code == 103 and f3 == 0
          branch = code == 99 and f3 != 2 and f3 != 3
          load = code == 3 and (f3 <= 2 or f3 == 4 or f3 == 5)
          store = code == 35 and f3 <= 2
          fence = code == 15 and f3 == 0
          ecall = insn == 115
          legal = (lui or auipc or jal or jalr or branch or load or store or imm
                   or reg or muldiv or fence or ecall)
          return {'lui': 1 if lui else 0, 'auipc': 1 if auipc else 0,
                  'jal': 1 if jal else 0, 'jalr': 1 if jalr else 0,
                  'branch': 1 if branch else 0, 'load': 1 if load else 0,
                  'store': 1 if store else 0, 'opimm': 1 if imm else 0,
                  'op': 1 if reg else 0, 'mul': 1 if muldiv and f3 < 4 else 0,
                  'div': 1 if muldiv and f3 >= 4 else 0,
                  'ecall': 1 if ecall else 0, 'illegal': 0 if legal else 1,
                  'alt': 1 if (reg or (imm and f3 == 5)) and f7 == 32 else 0}

.. source:: build/rtl/core/core_decode.v
   :implements: core.decode

   module core_decode (input wire [31:0] insn,
                       output wire lui, auipc, jal, jalr, branch, load, store, opimm, op, mul, div,
                       output wire ecall, illegal, alt);
       wire [6:0] code = insn[6:0], f7 = insn[31:25];
       wire [2:0] f3 = insn[14:12];
       wire shift = f3 == 3'd1 || f3 == 3'd5;
       wire base = f7 == 7'd0 || (f7 == 7'd32 && (f3 == 3'd0 || f3 == 3'd5));
       wire fence = code == 7'd15 && f3 == 3'd0;
       assign lui = code == 7'd55;
       assign auipc = code == 7'd23;
       assign jal = code == 7'd111;
       assign jalr = code == 7'd103 && f3 == 3'd0;
       assign branch = code == 7'd99 && f3 != 3'd2 && f3 != 3'd3;
       assign load = code == 7'd3 && f3 != 3'd3 && f3 < 3'd6;
       assign store = code == 7'd35 && f3 < 3'd3;
       assign opimm = code == 7'd19 && (!shift || f7 == 7'd0 || (f3 == 3'd5 && f7 == 7'd32));
       assign op = code == 7'd51 && base;
       assign mul = code == 7'd51 && f7 == 7'd1 && !f3[2];
       assign div = code == 7'd51 && f7 == 7'd1 && f3[2];
       assign ecall = insn == 32'h73;
       assign illegal = !(lui || auipc || jal || jalr || branch || load || store || opimm || op || mul
                          || div || fence || ecall);
       assign alt = (op || opimm && f3 == 3'd5) && f7 == 7'd32;
   endmodule

.. check:: equiv
   :verifies: core.decode
   :module: core_decode

.. requirement:: core.immediate
   :parent: design.economy

   The core shall take the immediate of an instruction from the bits that the format of its
   opcode defines.

   .. twin::
      :stamp: 1fb99d2b

      def extend(value, sign):
          return value | (4294967296 - sign * 2) if value >= sign else value
      def core_imm(insn):
          code = insn & 127
          top = insn >> 31
          i = insn >> 20
          s = ((insn >> 25) << 5) | ((insn >> 7) & 31)
          b = ((top << 12) | (((insn >> 7) & 1) << 11) | (((insn >> 25) & 63) << 5)
               | (((insn >> 8) & 15) << 1))
          u = (insn >> 12) << 12
          j = ((top << 20) | (((insn >> 12) & 255) << 12) | (((insn >> 20) & 1) << 11)
               | (((insn >> 21) & 1023) << 1))
          imm = (extend(i, 2048) if code == 3 or code == 19 or code == 103
                 else extend(s, 2048) if code == 35
                 else extend(b, 4096) if code == 99
                 else u if code == 23 or code == 55
                 else extend(j, 1048576) if code == 111 else 0)
          return {'imm': imm}

.. source:: build/rtl/core/core_imm.v
   :implements: core.immediate

   module core_imm (input wire [31:0] insn, output reg [31:0] imm);
       always @* case (insn[6:0])
           7'd3, 7'd19, 7'd103: imm = {{20{insn[31]}}, insn[31:20]};
           7'd35: imm = {{20{insn[31]}}, insn[31:25], insn[11:7]};
           7'd99: imm = {{19{insn[31]}}, insn[31], insn[7], insn[30:25], insn[11:8], 1'b0};
           7'd23, 7'd55: imm = {insn[31:12], 12'd0};
           7'd111: imm = {{11{insn[31]}}, insn[31], insn[19:12], insn[20], insn[30:21], 1'b0};
           default: imm = 32'd0;
       endcase
   endmodule

.. check:: equiv
   :verifies: core.immediate
   :module: core_imm

.. rationale::

   The decoder checks every field, not the opcode alone. An encoding outside ``RV32IM``, such as
   a read of a counter, then suspends its thread, and never runs as another instruction.

Arithmetic
==========

.. requirement:: core.alu
   :parent: design.economy

   The core shall compute the result of each register and immediate operation of ``RV32I`` as
   ``RV32I`` defines, from the ``f3`` field, the ``alt`` bit of its class and its two operands.

   .. twin::
      :stamp: 4fea14ab

      def signed(v):
          return v - 4294967296 if v >= 2147483648 else v
      def left(v, n):
          v1 = v << 1 if n & 1 != 0 else v
          v2 = v1 << 2 if n & 2 != 0 else v1
          v4 = v2 << 4 if n & 4 != 0 else v2
          v8 = v4 << 8 if n & 8 != 0 else v4
          return v8 << 16 if n & 16 != 0 else v8
      def right(v, n):
          v1 = v >> 1 if n & 1 != 0 else v
          v2 = v1 >> 2 if n & 2 != 0 else v1
          v4 = v2 >> 4 if n & 4 != 0 else v2
          v8 = v4 >> 8 if n & 8 != 0 else v4
          return v8 >> 16 if n & 16 != 0 else v8
      def core_alu(f3, alt, a, b):
          n = b & 31
          y = ((a - b if alt == 1 else a + b) if f3 == 0
               else left(a, n) if f3 == 1
               else (1 if signed(a) < signed(b) else 0) if f3 == 2
               else (1 if a < b else 0) if f3 == 3
               else a ^ b if f3 == 4
               else right(signed(a) if alt == 1 else a, n) if f3 == 5
               else a | b if f3 == 6 else a & b)
          return {'y': y & 4294967295}

.. source:: build/rtl/core/core_alu.v
   :implements: core.alu

   module core_alu (input wire [2:0] f3, input wire alt, input wire [31:0] a, b,
                    output reg [31:0] y);
       always @* case (f3)
           3'd0: y = alt ? a - b : a + b;
           3'd1: y = a << b[4:0];
           3'd2: y = {31'd0, $signed(a) < $signed(b)};
           3'd3: y = {31'd0, a < b};
           3'd4: y = a ^ b;
           3'd5: y = alt ? $unsigned($signed(a) >>> b[4:0]) : a >> b[4:0];
           3'd6: y = a | b;
           default: y = a & b;
       endcase
   endmodule

.. check:: equiv
   :verifies: core.alu
   :module: core_alu

.. requirement:: core.branch
   :parent: design.economy

   Where an instruction is a branch, the core shall take it when the condition of its ``f3``
   field holds for its two operands, as ``RV32I`` defines.

   .. twin::
      :stamp: 540f147e

      def signed(v):
          return v - 4294967296 if v >= 2147483648 else v
      def core_branch(f3, a, b):
          kind = f3 >> 1
          holds = (a == b if kind <= 1 else signed(a) < signed(b) if kind == 2
                   else a < b)
          return {'taken': (1 if holds else 0) ^ (f3 & 1)}

.. source:: build/rtl/core/core_branch.v
   :implements: core.branch

   module core_branch (input wire [2:0] f3, input wire [31:0] a, b, output wire taken);
       wire less = f3[1] ? a < b : $signed(a) < $signed(b);
       assign taken = (f3[2] ? less : a == b) ^ f3[0];
   endmodule

.. check:: equiv
   :verifies: core.branch
   :module: core_branch

.. rationale::

   Each operation is one expression of Verilog, and the tools map it to the logic of the chip.
   A shifter or a compare built by hand would be faster, and harder to read.

Multiply
========

.. requirement:: core.mul
   :parent: design.economy

   Where an instruction is a multiply, the core shall give the half of the product of its two
   operands that ``RV32M`` defines for its ``f3`` field.

   .. twin::
      :stamp: 58a00296

      def core_mul(f3, a, b):
          x = a - 4294967296 if f3 != 3 and a >= 2147483648 else a
          z = b - 4294967296 if f3 < 2 and b >= 2147483648 else b
          p = x * z
          return {'y': p & 4294967295 if f3 == 0 else (p >> 32) & 4294967295}
      def core_mul_split(f3, a, b):
          al = a & 65535
          bl = b & 65535
          ah = (a >> 16) - 65536 if f3 != 3 and a >= 2147483648 else a >> 16
          bh = (b >> 16) - 65536 if f3 < 2 and b >= 2147483648 else b >> 16
          p = al * bl + ((al * bh) << 16) + ((ah * bl) << 16) + ((ah * bh) << 32)
          return {'y': p & 4294967295 if f3 == 0 else (p >> 32) & 4294967295}

.. source:: build/rtl/core/core_mul_part.v
   :implements: core.mul

   module core_mul_part (input wire [1:0] f3, input wire [31:0] a, b,
                         output wire [35:0] ll, lh, hl, hh);
       wire [17:0] ah = {{2{f3 != 2'd3 && a[31]}}, a[31:16]};
       wire [17:0] bh = {{2{!f3[1] && b[31]}}, b[31:16]};
       assign ll = a[15:0] * b[15:0];
       assign lh = $signed({2'b0, a[15:0]}) * $signed(bh);
       assign hl = $signed(ah) * $signed({2'b0, b[15:0]});
       assign hh = $signed(ah) * $signed(bh);
   endmodule

.. source:: build/rtl/core/core_mul_sum.v
   :implements: core.mul

   module core_mul_sum (input wire [1:0] f3, input wire [35:0] ll, lh, hl, hh,
                        output wire [31:0] y);
       wire [63:0] p = {28'd0, ll} + ({{28{lh[35]}}, lh} << 16) + ({{28{hl[35]}}, hl} << 16)
                     + ({{28{hh[35]}}, hh} << 32);
       assign y = f3 == 2'd0 ? p[31:0] : p[63:32];
   endmodule

.. source:: build/rtl/core/core_mul.v
   :implements: core.mul

   module core_mul (input wire [1:0] f3, input wire [31:0] a, b, output wire [31:0] y);
       wire [35:0] ll, lh, hl, hh;
       core_mul_part part (.f3, .a, .b, .ll, .lh, .hl, .hh);
       core_mul_sum sum (.f3, .ll, .lh, .hl, .hh, .y);
   endmodule

.. check:: equiv
   :verifies: core.mul
   :module: core_mul
   :twin: core_mul_split

.. rationale::

   The pipeline puts a register between the partial products and their sum, so each half
   fits in a cycle. ``core_mul_split`` states those steps, and the check proves them equal to
   the product.

Memory access
=============

.. requirement:: core.load
   :parent: design.economy

   Where an instruction is a load, the core shall take the bytes that its ``f3`` field selects
   from the word at its address, and extend the value as ``RV32I`` defines.

   .. twin::
      :stamp: 3ad13599

      def core_load(f3, lo, word):
          s = (word >> 8 if lo == 1 else word >> 16 if lo == 2
               else word >> 24 if lo == 3 else word)
          size = f3 & 3
          byte = s & 255
          half = s & 65535
          y = ((byte | 4294967040 if f3 < 4 and byte >= 128 else byte) if size == 0
               else (half | 4294901760 if f3 < 4 and half >= 32768 else half)
               if size == 1 else s)
          return {'y': y}

.. source:: build/rtl/core/core_load.v
   :implements: core.load

   module core_load (input wire [2:0] f3, input wire [1:0] lo, input wire [31:0] word,
                     output wire [31:0] y);
       wire [31:0] s = word >> {lo, 3'd0};
       assign y = f3[1:0] == 2'd0 ? {{24{!f3[2] && s[7]}}, s[7:0]}
                : f3[1:0] == 2'd1 ? {{16{!f3[2] && s[15]}}, s[15:0]} : s;
   endmodule

.. check:: equiv
   :verifies: core.load
   :module: core_load

.. requirement:: core.store
   :parent: design.economy

   Where an instruction is a store, the core shall write the bytes that its ``f3`` field
   selects to the word at its address, and leave its other bytes.

   .. twin::
      :stamp: f30bb71e

      def core_store(size, lo, data):
          byte = data & 255
          half = data & 65535
          be = ((1 if lo == 0 else 2 if lo == 1 else 4 if lo == 2 else 8) if size == 0
                else (3 if lo == 0 else 6 if lo == 1 else 12 if lo == 2 else 8)
                if size == 1 else 15)
          wdata = (byte * 16843009 if size == 0 else half * 65537 if size == 1
                   else data)
          return {'be': be, 'wdata': wdata}

.. source:: build/rtl/core/core_store.v
   :implements: core.store

   module core_store (input wire [1:0] size, input wire [1:0] lo, input wire [31:0] data,
                      output wire [3:0] be, output wire [31:0] wdata);
       assign be = size == 2'd0 ? 4'b0001 << lo : size == 2'd1 ? 4'b0011 << lo : 4'b1111;
       assign wdata = size == 2'd0 ? {4{data[7:0]}} : size == 2'd1 ? {2{data[15:0]}} : data;
   endmodule

.. check:: equiv
   :verifies: core.store
   :module: core_store

.. requirement:: core.misaligned
   :parent: design.economy

   Where the address of a load or a store is not a multiple of the size of its access, the
   core shall refuse the access.

   .. twin::
      :stamp: 9310d59b

      def core_misaligned(size, lo):
          span = 1 if size == 0 else 2 if size == 1 else 4 if size == 2 else 8
          return {'fault': 0 if lo & (span - 1) == 0 else 1}

.. source:: build/rtl/core/core_misaligned.v
   :implements: core.misaligned

   module core_misaligned (input wire [1:0] size, input wire [1:0] lo, output wire fault);
       assign fault = (size[1] && lo != 2'd0) || (size[0] && lo[0]);
   endmodule

.. check:: equiv
   :verifies: core.misaligned
   :module: core_misaligned

.. rationale::

   ``RV32I`` lets a core refuse an access that is not aligned. The supervisor can do the
   access for the thread, so the hardware needs no second cycle and no second port.

Divide
======

.. requirement:: core.div
   :parent: design.economy

   Where an instruction is a divide or a remainder, the core shall give the result that
   ``RV32M`` defines for its ``f3`` field and its two operands.

.. requirement:: core.div-time
   :parent: design.timing-invariant

   When a thread starts a divide, the core shall fetch nothing in each turn of the thread in the
   38 cycles after the turn of the divide, for any operands and any work of the other threads.
   The 38 cycles are 4 before the steps of the divide, its 32 steps, and 2 to write its result.

   .. twin::
      :stamp: 737329e7

      def core_div_time():
          end = 4 + 32 + 2
          return {'turns': end // CORE_THREADS}

.. source:: build/rtl/core/core_div_time.v

   // The prove of the core checks that a divide skips this number of turns.
   module core_div_time (output wire [2:0] turns);
       assign turns = 3'((4 + 32 + 2) / bcw_params::CORE_THREADS);
   endmodule

.. check:: equiv
   :verifies: core.div-time
   :module: core_div_time

.. requirement:: core.div-step
   :parent: core.div

   The core shall find one bit of the quotient in each step of a divide: it subtracts the
   divisor from the remainder where the divisor fits.

   .. twin::
      :stamp: 3c878b7a

      def core_div_step(r, q, d):
          t = r * 2 + (q >> 31)
          fits = t >= d
          return {'r_next': (t - d if fits else t) & 4294967295,
                  'q_next': ((q << 1) & 4294967295) | (1 if fits else 0)}

.. source:: build/rtl/core/core_div_step.v
   :implements: core.div-step

   module core_div_step (input wire [31:0] r, q, d, output wire [31:0] r_next, q_next);
       wire [32:0] t = {r, q[31]};
       wire fits = t >= {1'b0, d};
       assign r_next = fits ? 32'(t - {1'b0, d}) : t[31:0];
       assign q_next = {q[30:0], fits};
   endmodule

.. check:: equiv
   :verifies: core.div-step
   :module: core_div_step

.. source:: build/rtl/core/core_div_unit.v
   :implements: core.div, core.div-time

   // The divider of one thread, which only its own requests and its own write reach.
   module core_div_unit (input wire clk, rst_n, start, input wire [1:0] f3, input wire [31:0] a, b,
                         input wire [4:0] start_rd, output logic [31:0] value, output wire [4:0] rd,
                         output wire [5:0] steps);
       logic [31:0] r, q, d;
       logic [5:0] count;
       logic negate, remainder;
       logic [4:0] dest;
       wire [31:0] r_next, q_next;
       wire sa = !f3[0] && a[31], sb = !f3[0] && b[31];
       core_div_step step (.r, .q, .d, .r_next, .q_next);
       always_ff @(posedge clk)
           if (!rst_n) count <= '0;
           else if (start) begin
               {r, q, d, count} <= {32'd0, sa ? -a : a, sb ? -b : b, 6'd32};
               remainder <= f3[1];
               negate <= f3[1] ? sa : sa != sb && b != 32'd0;
               dest <= start_rd;
           end else if (count != '0) {r, q, count} <= {r_next, q_next, count - 6'd1};
       // The unit negates its result a cycle after each step, so that no adder follows the choice of a
       // result in core_div: that choice held the critical path. The core reads a result two cycles
       // after the last step, and the proof of the core checks that it reads this one.
       always_ff @(posedge clk) value <= negate ? -(remainder ? r : q) : (remainder ? r : q);
       assign {rd, steps} = {dest, count};
   endmodule

.. source:: build/rtl/core/core_div.v
   :implements: core.div, core.div-time

   module core_div (input wire clk, rst_n, req, input wire [bcw_params::CORE_TURN_WIDTH-1:0] req_thread,
                    input wire [1:0] f3, input wire [31:0] a, b, input wire [4:0] req_rd,
                    input wire [bcw_params::CORE_TURN_WIDTH-1:0] thread, look_thread,
                    output wire [31:0] result, look_result, output wire [4:0] rd,
                    output wire [bcw_params::CORE_THREADS-1:0][5:0] steps);
       localparam int T = bcw_params::CORE_THREADS;
       wire [31:0] value [T];
       wire [4:0] dest [T];
       for (genvar t = 0; t < T; t++) begin : units
           core_div_unit unit (.clk, .rst_n, .start(req && req_thread == t), .f3, .a, .b, .start_rd(req_rd),
                               .value(value[t]), .rd(dest[t]), .steps(steps[t]));
       end
       assign result = value[thread];
       assign rd = dest[thread];
       // The port reads the result of any one thread.
       assign look_result = value[look_thread];
   endmodule

.. mutant:: build/rtl/core/core_div_unit.v
   :kills: core.registers.test

   -            negate <= f3[1] ? sa : sa != sb && b != 32'd0;
   +            negate <= f3[1] ? sa : sa != sb;

.. mutant:: build/rtl/core/core_div_unit.v
   :kills: core.depth.prove

   -            {r, q, d, count} <= {32'd0, sa ? -a : a, sb ? -b : b, 6'd32};
   +            {r, q, d, count} <= {32'd0, sa ? -a : a, sb ? -b : b, 6'd33};

.. rationale::

   One step for each thread in each cycle gives a fixed time of 32 cycles. The thread waits for
   the steps, not for a count of turns that could be too short. ``bcw-1`` took 9 turns.

Contexts
========

.. definition:: core.context
   :parent: core.core

   A :dfn:`context` is a set of 32 registers of 32 bits, a program counter and a region.

.. parameter:: core.thread-contexts
   :parent: core.context
   :value: 2

   The number of contexts of each thread.

.. definition:: core.selector
   :parent: core.context

   The :dfn:`selector` of a thread names which of its own contexts the thread runs.

.. parameter:: core.select-width
   :parent: core.thread-contexts
   :value: clog2(core.thread-contexts)
   :unit: bits

   The width of a selector.

.. definition:: core.index
   :parent: core.context

   The :dfn:`index` of a thread is the number of the context that holds its registers.

.. parameter:: core.contexts
   :parent: core.context
   :value: core.threads * core.thread-contexts

   The number of contexts that the core holds.

.. parameter:: core.context-width
   :parent: core.contexts
   :value: clog2(core.contexts)
   :unit: bits

   The width of an index.

.. requirement:: core.own-contexts
   :parent: design.isolation

   The core shall form the index of a thread from the number of the thread and its selector.

.. requirement:: core.own-pc
   :parent: design.isolation

   The core shall change the program counter of a context only for an instruction that runs in
   the context, or a write to the context.

.. rationale::

   A context holds a whole process, so a switch between two processes is one write of the
   selector.

Registers
=========

.. requirement:: core.registers
   :parent: design.economy

   The core shall hold :param:`core.contexts` contexts, and read register 0 as zero.

.. requirement:: core.register-write
   :parent: design.timing-invariant

   When the core writes a register, the core shall change no other register.

.. source:: build/rtl/core/core_regfile.v
   :implements: core.registers, core.register-write

   module core_regfile (input wire clk,
                        input wire [bcw_params::CORE_CONTEXT_WIDTH+4:0] ra, rb, wa,
                        input wire we, input wire [31:0] wd, output wire [31:0] a, b);
       logic [31:0] bank_a [2 ** (bcw_params::CORE_CONTEXT_WIDTH + 5)];
       logic [31:0] bank_b [2 ** (bcw_params::CORE_CONTEXT_WIDTH + 5)];
       logic [31:0] read_a, read_b;
       logic zero_a, zero_b;
       always_ff @(posedge clk) begin
           if (we) begin
               bank_a[wa] <= wd;
               bank_b[wa] <= wd;
           end
           read_a <= bank_a[ra];
           read_b <= bank_b[rb];
           zero_a <= ra[4:0] == 5'd0;
           zero_b <= rb[4:0] == 5'd0;
       end
       assign a = zero_a ? 32'd0 : read_a;
       assign b = zero_b ? 32'd0 : read_b;
   `ifdef FORMAL
       // A proof sees only the ports, and the memory hides what it holds, so the file states its own
       // invariant: it follows any one register, which both banks hold and each read gives.
       (* anyconst *) logic [bcw_params::CORE_CONTEXT_WIDTH+4:0] f_reg;
       logic [bcw_params::CORE_CONTEXT_WIDTH+4:0] f_ra, f_rb;
       logic [31:0] f_value, f_was;
       logic f_known = 1'b0, f_knew = 1'b0, f_read = 1'b0;
       always_ff @(posedge clk) begin
           if (we && wa == f_reg) {f_value, f_known} <= {wd, 1'b1};
           {f_was, f_knew, f_ra, f_rb, f_read} <= {f_value, f_known, ra, rb, 1'b1};
       end
       wire [31:0] f_want = f_reg[4:0] == 5'd0 ? 32'd0 : f_was;
       wire f_valid = f_read && (f_knew || f_reg[4:0] == 5'd0);
       always_comb if (f_known) assert (bank_a[f_reg] == f_value && bank_b[f_reg] == f_value);
       always_comb if (f_valid && f_ra == f_reg) assert (a == f_want);
       always_comb if (f_valid && f_rb == f_reg) assert (b == f_want);
   `endif
   endmodule

.. mutant:: build/rtl/core/core_regfile.v
   :kills: core.depth.prove

   -            bank_b[wa] <= wd;
   +            bank_b[rb] <= wd;

.. requirement:: core.own-context
   :parent: design.timing-invariant

   The core shall reach the registers of a thread only through its index.

.. rationale::

   Two copies of the registers give two reads in one cycle from the block memory of the chip.
   Register 0 reads as zero by a compare, not by the contents of the memory.

Regions
=======

.. requirement:: core.regions
   :parent: memory.supervisor

   The core shall give thread 0 the supervisor part as its region.

.. requirement:: core.address
   :parent: memory.workers

   The core shall address the supervisor part for thread 0 and the worker part for each other
   thread, at the address that the thread gives from the base of its region, in the part.

.. requirement:: core.region-check
   :parent: design.isolation

   If a byte of a fetch or an access is outside its region, then the core shall refuse it.

   .. twin::
      :stamp: c4903815

      def core_region(offset, size, bound):
          return {'out': 1 if offset + size > bound else 0}

.. source:: build/rtl/core/core_region.v
   :implements: core.region-check

   module core_region (input wire [31:0] offset, input wire [2:0] size,
                       input wire [bcw_params::MEMORY_PART_WIDTH:0] bound, output wire out);
       assign out = 33'(offset) + 33'(size) > 33'(bound);
   endmodule

.. check:: equiv
   :verifies: core.region-check
   :module: core_region

.. requirement:: core.size-word
   :parent: memory.worker-part

   When thread 0 loads the last word of the supervisor part, the core shall give
   :param:`memory.worker-part` as the word.

.. rationale::

   The part of an address is the number of its thread, not a compare, so no other thread can
   reach the supervisor part. The supervisor learns the size of the worker part with one load.

Pipeline
========

.. definition:: core.stage
   :parent: core.core

   A :dfn:`stage` is one cycle of the work on an instruction. The core has 8 stages: fetch,
   expand, decode, read, execute, address, data and write.

.. requirement:: core.depth
   :parent: design.economy

   The core shall finish each instruction of a thread before the next turn of the thread.

.. requirement:: core.issue
   :parent: design.timing-invariant

   While a thread runs with no divide, the core shall start an instruction of the thread in each
   turn of the thread.

.. schedule:: The thread whose instruction each stage holds in each cycle of one rotation, with thread 0 fetching in cycle 0. The proof of the core shows this for any thread.
   :threads: core.threads
   :module: core
   :private: threads units

   fetch
   expand: x_
   decode: d_
   read: r_
   execute: e_
   address: m1_
   data: m2_
   write, which alone writes the registers: w_

   rot: the thread of the turn, which counts cycles and no thread changes
   q_we q_index q_field q_data: a store of thread 0 to a control block

.. requirement:: core.step
   :parent: design.economy

   When an instruction finishes, the core shall change the state of its thread as one step
   of ``RV32IMC`` from the word of the instruction, its program counter, its registers and
   its loaded word.

.. source:: build/rtl/core/core_expand.v
   :implements: core.step

   module core_expand (input wire [31:0] word, output wire [31:0] insn, output wire illegal, wide);
       wire [31:0] i0, i1, i2;
       wire b0, b1, b2;
       core_rvc0 q0 (.c(word[15:0]), .insn(i0), .illegal(b0));
       core_rvc1 q1 (.c(word[15:0]), .insn(i1), .illegal(b1));
       core_rvc2 q2 (.c(word[15:0]), .insn(i2), .illegal(b2));
       assign wide = word[1:0] == 2'd3;
       assign {insn, illegal} = word[1:0] == 2'd0 ? {i0, b0} : word[1:0] == 2'd1 ? {i1, b1}
                              : word[1:0] == 2'd2 ? {i2, b2} : {word, 1'b0};
   endmodule

.. source:: build/rtl/core/core.v
   :implements: core.depth, core.issue, core.own-state, core.step, core.suspend, core.div-wait,
                core.control-write, core.control-read, core.reset, core.reset-quiet, core.own-context, core.address,
                core.region-check, core.size-word

   module core (input wire clk, rst_n, output wire [bcw_params::CORE_TURN_WIDTH-1:0] turn,
                output wire [bcw_params::MEMORY_PART_WIDTH:0] fetch_addr, input wire [31:0] fetch_word,
                output wire [bcw_params::MEMORY_PART_WIDTH:0] data_addr, output wire [3:0] data_be, output wire data_we,
                output wire [31:0] data_wdata, input wire [31:0] data_rdata,
                input wire [bcw_params::CORE_TURN_WIDTH-1:0] watch_thread, output wire [2:0] watch_state,
                output wire [5:0] watch_steps, output wire [31:0] watch_result,
                output wire [bcw_params::CORE_THREAD_CONTEXTS-1:0][31:0] watch_pcs, output wire [bcw_params::MEMORY_PART_WIDTH-1:0] watch_base,
                output wire [bcw_params::MEMORY_PART_WIDTH:0] watch_bound,
                output wire [bcw_params::CORE_SELECT_WIDTH-1:0] watch_select,
                output wire [bcw_params::CORE_CONTEXT_WIDTH+4:0] ra, rb, wa, output wire we,
                output wire [31:0] wd, input wire [31:0] a, b,
                output wire commit, commit_resume, output wire [1:0] commit_cause,
                output wire [bcw_params::CORE_TURN_WIDTH-1:0] commit_thread,
                output wire [31:0] commit_pc, commit_word, commit_a, commit_b, commit_addr, commit_load,
                output wire [31:0] commit_next, mul_a, mul_b);
       localparam int T = bcw_params::CORE_THREADS, TW = bcw_params::CORE_TURN_WIDTH;
       localparam int CW = bcw_params::CORE_CONTEXT_WIDTH, PW = bcw_params::MEMORY_PART_WIDTH;
       localparam int SW = bcw_params::CORE_SELECT_WIDTH;
       localparam logic [1:0] NONE = 2'd0, REQUEST = 2'd1, REFUSED = 2'd2;

       // The state of each thread, which only the stage W, the divider and the port write.
       wire [T-1:0][31:0] pc;
       wire [T-1:0][bcw_params::CORE_THREAD_CONTEXTS-1:0][31:0] pcs;
       wire [T-1:0][PW-1:0] base;
       wire [T-1:0][PW:0] bound;
       wire [T-1:0][bcw_params::CORE_THREAD_CONTEXTS-1:0][PW-1:0] bases;
       wire [T-1:0][bcw_params::CORE_THREAD_CONTEXTS-1:0][PW:0] bounds;
       wire [T-1:0][2:0] state;
       wire [T-1:0] fetching, waiting;
       wire [T-1:0][5:0] steps;
       wire [T-1:0][CW-1:0] index;
       wire [T-1:0][bcw_params::CORE_SELECT_WIDTH-1:0] select;
       logic [TW-1:0] rot, rot_next;
       core_rotate rotate (.turn(rot), .next(rot_next));
       assign turn = rot;

       // F: fetch the word at the program counter of the thread of the turn.
       assign fetch_addr = {rot == '0, PW'(base[rot] + pc[rot][PW-1:0])};
       logic x_v; logic [TW-1:0] x_t; logic [31:0] x_pc;

       // X: expand a compressed instruction.
       wire [31:0] x_insn;
       wire x_bad, x_wide;
       core_expand expand (.word(fetch_word), .insn(x_insn), .illegal(x_bad), .wide(x_wide));
       logic d_v, d_bad, d_wide; logic [TW-1:0] d_t; logic [31:0] d_pc, d_insn, d_word;

       // D: decode, and read the registers.
       wire lui, auipc, jal, jalr, branch, load, store, opimm, op, mul, div, ecall, illegal, alt;
       wire [31:0] d_imm;
       core_decode decode (.insn(d_insn), .lui, .auipc, .jal, .jalr, .branch, .load, .store, .opimm, .op,
                           .mul, .div, .ecall, .illegal, .alt);
       core_imm immediate (.insn(d_insn), .imm(d_imm));
       wire d_out;
       core_region fetch_region (.offset(d_pc), .size(d_wide ? 3'd4 : 3'd2), .bound(bound[d_t]), .out(d_out));
       assign ra = {index[d_t], d_insn[19:15]};
       assign rb = {index[d_t], d_insn[24:20]};
       logic r_v, r_wide, r_alt; logic [10:0] r_class; logic [1:0] r_cause; logic [TW-1:0] r_t;
       logic [31:0] r_pc, r_imm, r_word; logic [14:7] r_insn;

       // R: the registers arrive.
       logic e_v, e_wide, e_alt; logic [10:0] e_class; logic [1:0] e_cause; logic [TW-1:0] e_t;
       logic [31:0] e_pc, e_imm, e_word, e_a, e_b, e_bi; logic [14:7] e_insn;

       // E: execute. The class bits are, in order, lui auipc jal jalr branch load store opimm op mul div.
       wire e_lui = e_class[10], e_auipc = e_class[9], e_jal = e_class[8], e_jalr = e_class[7];
       wire e_branch = e_class[6], e_load = e_class[5], e_store = e_class[4], e_opimm = e_class[3];
       wire e_mul = e_class[1], e_div = e_class[0];
       wire [2:0] f3 = e_insn[14:12];
       wire [31:0] alu_y, sum = e_a + e_imm, link = e_pc + (e_wide ? 32'd4 : 32'd2);
       wire taken, fault;
       // R chooses the second operand of the ALU, the immediate or the register: in E, that choice
       // held the critical path.
       core_alu alu (.f3, .alt(e_alt), .a(e_a), .b(e_bi), .y(alu_y));
       core_branch compare (.f3, .a(e_a), .b(e_b), .taken);
       core_misaligned align (.size(f3[1:0]), .lo(sum[1:0]), .fault);
       wire e_out;
       core_region data_region (.offset(sum), .size(3'd1 << f3[1:0]), .bound(bound[e_t]), .out(e_out));
       wire [31:0] next = e_jal || e_branch && taken ? e_pc + e_imm : e_jalr ? {sum[31:1], 1'b0} : link;
       wire [1:0] e_stop = e_cause != NONE ? e_cause : (e_load || e_store) && (fault || e_out) ? REFUSED : NONE;
       // The choice between the ALU and the other results waits for M1, which has time to spare: after
       // the ALU, it held the critical path.
       wire [31:0] e_other = e_lui ? e_imm : e_auipc ? e_pc + e_imm : link;
       wire e_pick = e_class[10:7] != 4'd0;
       wire e_we = e_class[10:7] != 4'd0 || e_load || e_opimm || e_class[2] || e_mul;
       wire [31:0] div_result;
       wire [4:0] div_rd;
       wire resume, start = e_v && e_div && e_cause == NONE;
       core_div divide (.clk, .rst_n, .req(start), .req_thread(e_t), .f3(f3[1:0]),
                        .a(e_a), .b(e_b), .req_rd(e_insn[11:7]), .thread(rot_next), .look_thread(watch_thread),
                        .result(div_result), .look_result(watch_result), .rd(div_rd), .steps);
       logic m1_v, m1_we, m1_load, m1_store, m1_mul; logic [1:0] m1_cause; logic [TW-1:0] m1_t;
       logic [4:0] m1_rd; logic [2:0] m1_f3; logic [31:0] m1_pc, m1_word, m1_a, m1_b, m1_addr, m1_res, m1_next, m1_other;
       logic m1_pick;

       // M1: send the address of the data, form the partial products, and choose the result.
       wire m1_hit;
       wire [CW-1:0] m1_index;
       wire [1:0] m1_field;
       core_control control (.addr(m1_addr[31:2]), .hit(m1_hit), .index(m1_index), .field(m1_field));
       // Thread 0 reads a word of a control block here in M1: in M2 the choice held the critical path.
       wire [TW-1:0] m1_thread = m1_index[CW-1:SW];
       wire [SW-1:0] m1_select = m1_index[SW-1:0];
       wire [31:0] m1_read = m1_field == 2'd0 ? pcs[m1_thread][m1_select]
                           : m1_field == 2'd1 ? 32'(bases[m1_thread][m1_select])
                           : m1_field == 2'd2 ? 32'(bounds[m1_thread][m1_select])
                           : 32'({select[m1_thread], 1'b0, state[m1_thread]});
       wire [35:0] ll, lh, hl, hh;
       // The multiplier reads its operands through mul_a and mul_b, which the proofs see.
       assign {mul_a, mul_b} = {m1_a, m1_b};
       core_mul_part part (.f3(m1_f3[1:0]), .a(mul_a), .b(mul_b), .ll, .lh, .hl, .hh);
       core_store place (.size(m1_f3[1:0]), .lo(m1_addr[1:0]), .data(m1_b), .be(data_be), .wdata(data_wdata));
       assign data_addr = {m1_t == '0, PW'(base[m1_t] + m1_addr[PW-1:0])};
       assign data_we = rst_n && m1_v && m1_store && m1_cause == NONE;
       logic m2_v, m2_we, m2_load, m2_mul, m2_control; logic [31:0] m2_read; logic [1:0] m2_cause; logic [TW-1:0] m2_t;
       logic [4:0] m2_rd; logic [2:0] m2_f3; logic [31:0] m2_pc, m2_word, m2_a, m2_b, m2_addr, m2_res, m2_next;
       logic [35:0] m2_ll, m2_lh, m2_hl, m2_hh;

       // M2: the loaded word arrives, and the partial products add up.
       wire [31:0] product;
       core_mul_sum total (.f3(m2_f3[1:0]), .ll(m2_ll), .lh(m2_lh), .hl(m2_hl), .hh(m2_hh), .y(product));
       // The last word of the supervisor part reads as the size of the worker part.
       wire m2_size = m2_t == '0 && m2_addr[31:2] == 30'(bcw_params::MEMORY_SUPERVISOR_PART / 4 - 1);
       logic w_v, w_we_r, w_load; logic [1:0] w_cause; logic [TW-1:0] w_t; logic [4:0] w_rd;
       logic [2:0] w_f3; logic [31:0] w_pc, w_word, w_a, w_b, w_addr, w_res, w_next, w_data;

       // W: the one place that an instruction changes the state of its thread.
       wire [31:0] loaded;
       core_load extract (.f3(w_f3), .lo(w_addr[1:0]), .word(w_data), .y(loaded));
       wire retire = w_v && w_cause == NONE;
       // A thread resumes in its write slot once its divider has finished all its steps.
       assign resume = waiting[rot_next] && steps[rot_next] == 6'd0;
       assign we = rst_n && (retire && w_we_r || resume);
       assign wa = resume ? {index[rot_next], div_rd} : {index[w_t], w_rd};
       assign wd = resume ? div_result : w_load ? loaded : w_res;

       // Each change of the state of a thread, for the proofs and the tests.
       assign {commit, commit_resume, commit_cause, commit_thread}
           = {w_v || resume, resume, resume ? NONE : w_cause, resume ? rot_next : w_t};
       assign {commit_pc, commit_word, commit_a, commit_b, commit_addr, commit_load, commit_next}
           = {w_pc, w_word, w_a, w_b, w_addr, w_data, w_next};

       // A word store of thread 0 to a control block writes the thread one cycle later.
       logic q_we; logic [CW-1:0] q_index; logic [1:0] q_field; logic [31:0] q_data;
       assign {watch_pcs, watch_base, watch_bound, watch_state, watch_steps, watch_select}
           = {pcs[watch_thread], base[watch_thread], bound[watch_thread], state[watch_thread],
              steps[watch_thread], select[watch_thread]};

       always_ff @(posedge clk) begin
           rot <= rst_n ? rot_next : '0;
           {q_we, q_index, q_field, q_data} <= {rst_n && m1_v && m1_store && m1_cause == NONE && m1_t == '0 && m1_hit
                                                && m1_f3 == 3'd2, m1_index, m1_field, m1_b};
           {m2_control, m2_read} <= {m1_t == '0 && m1_hit, m1_read};
           {x_v, x_t, x_pc} <= {rst_n && fetching[rot], rot, pc[rot]};
           {d_v, d_t, d_pc, d_insn, d_word, d_bad, d_wide} <= {rst_n && x_v, x_t, x_pc, x_insn, fetch_word, x_bad, x_wide};
           {r_v, r_t, r_pc, r_word, r_insn, r_imm, r_wide, r_alt} <= {rst_n && d_v, d_t, d_pc, d_word, d_insn[14:7],
                                                                      d_imm, d_wide, alt};
           r_class <= {lui, auipc, jal, jalr, branch, load, store, opimm, op, mul, div};
           r_cause <= d_out ? REFUSED : ecall ? REQUEST : d_bad || illegal ? REFUSED : NONE;
           {e_v, e_t, e_pc, e_word, e_insn, e_imm, e_wide, e_alt, e_class, e_cause, e_a, e_b}
               <= {rst_n && r_v, r_t, r_pc, r_word, r_insn, r_imm, r_wide, r_alt, r_class, r_cause, a, b};
           e_bi <= r_class[3] ? r_imm : b;
           {m1_v, m1_t, m1_pc, m1_word, m1_a, m1_b, m1_cause, m1_rd, m1_f3, m1_addr, m1_res, m1_next}
               <= {rst_n && e_v, e_t, e_pc, e_word, e_a, e_b, e_stop, e_insn[11:7], f3, sum, alu_y, next};
           {m1_other, m1_pick} <= {e_other, e_pick};
           {m1_we, m1_load, m1_store, m1_mul} <= {e_we, e_load, e_store, e_mul};
           {m2_v, m2_t, m2_pc, m2_word, m2_a, m2_b, m2_cause, m2_rd, m2_f3, m2_addr, m2_res, m2_next}
               <= {rst_n && m1_v, m1_t, m1_pc, m1_word, m1_a, m1_b, m1_cause, m1_rd, m1_f3, m1_addr,
                   m1_pick ? m1_other : m1_res, m1_next};
           {m2_we, m2_load, m2_mul, m2_ll, m2_lh, m2_hl, m2_hh} <= {m1_we, m1_load, m1_mul, ll, lh, hl, hh};
           {w_v, w_t, w_pc, w_word, w_a, w_b, w_cause, w_rd, w_f3, w_addr, w_next, w_data}
               <= {rst_n && m2_v, m2_t, m2_pc, m2_word, m2_a, m2_b, m2_cause, m2_rd, m2_f3, m2_addr, m2_next,
                   m2_control ? m2_read : m2_size ? 32'(bcw_params::MEMORY_WORKER_PART) : data_rdata};
           {w_we_r, w_load, w_res} <= {m2_we, m2_load, m2_mul ? product : m2_res};
       end

       for (genvar t = 0; t < T; t++) begin : threads
           core_thread #(.ID(t)) thread (.clk, .rst_n, .commit(w_v && w_t == t), .why(w_cause), .slot(rot_next == t),
                                         .start(start && e_t == t), .done(resume && rot_next == t), .next(w_next),
                                         .put(q_we && q_index[CW-1:SW] == t), .put_select(q_index[SW-1:0]),
                                         .put_field(q_field), .put_data(q_data), .pcs(pcs[t]), .bases(bases[t]),
                                         .bounds(bounds[t]), .pc(pc[t]), .base(base[t]), .bound(bound[t]),
                                         .state(state[t]), .select(select[t]), .index(index[t]));
           // A thread fetches while it runs or stops, and waits while its divide runs.
           assign {fetching[t], waiting[t]} = {state[t][2:1] == 2'b00, state[t][2:1] == 2'b01};
       end
   endmodule

.. source:: build/rtl/core/core_top.v

   // The core with its registers, as make timing places and routes it. It keeps each port of the
   // core, so that synthesis leaves out none of its logic.
   module core_top (input wire clk, rst_n, output wire [bcw_params::CORE_TURN_WIDTH-1:0] turn,
                    output wire [bcw_params::MEMORY_PART_WIDTH:0] fetch_addr, input wire [31:0] fetch_word,
                    output wire [bcw_params::MEMORY_PART_WIDTH:0] data_addr, output wire [3:0] data_be, output wire data_we,
                    output wire [31:0] data_wdata, input wire [31:0] data_rdata,
                    input wire [bcw_params::CORE_TURN_WIDTH-1:0] watch_thread, output wire [2:0] watch_state,
                    output wire [5:0] watch_steps, output wire [31:0] watch_result,
                    output wire [bcw_params::CORE_THREAD_CONTEXTS-1:0][31:0] watch_pcs, output wire [bcw_params::MEMORY_PART_WIDTH-1:0] watch_base,
                    output wire [bcw_params::MEMORY_PART_WIDTH:0] watch_bound, output wire [bcw_params::CORE_SELECT_WIDTH-1:0] watch_select,
                    output wire commit, commit_resume, output wire [1:0] commit_cause,
                    output wire [bcw_params::CORE_TURN_WIDTH-1:0] commit_thread,
                    output wire [31:0] commit_pc, commit_word, commit_a, commit_b, commit_addr, commit_load,
                    output wire [31:0] commit_next, mul_a, mul_b);
       wire [bcw_params::CORE_CONTEXT_WIDTH+4:0] ra, rb, wa;
       wire we;
       wire [31:0] wd, a, b;
       core dut (.*);
       core_regfile regs (.*);
   endmodule

.. check:: prove
   :verifies: core.depth, core.issue, core.own-state, core.own-context, core.step, core.suspend,
              core.div-wait, core.div-time, core.index-write, core.own-contexts, core.registers,
              core.register-write, core.reset-quiet, core.stop, core.state-change, core.own-pc,
              core.regions, core.address, core.region-check, core.size-word, core.control-write
   :depth: 10

   module core_props (input wire clk, input wire [31:0] fetch_word, data_rdata);
       logic rst_n = 1'b0;
       always_ff @(posedge clk) rst_n <= 1'b1;
       wire [2:0] turn, commit_thread;
       wire [16:0] fetch_addr, data_addr;
       wire [31:0] data_wdata;
       wire [1:0][31:0] watch_pcs;
       wire [15:0] watch_base;
       wire [16:0] watch_bound;
       wire [3:0] data_be;
       wire data_we, commit, commit_resume, we;
       wire [1:0] commit_cause;
       wire [2:0] watch_state;
       wire watch_select;
       wire [8:0] ra, rb, wa;
       wire [5:0] watch_steps;
       wire [31:0] watch_result, mul_a, mul_b, wd, a, b, commit_pc, commit_word, commit_a, commit_b, commit_addr, commit_load, commit_next;
       // The registers are outside the core, so that their reads and writes are ports, and the proof
       // holds the core with the real registers, whose own invariant it checks there. The port reads
       // any one thread, which the proof watches.
       (* anyconst *) logic [2:0] watched;
       wire [2:0] watch_thread = watched;
       // core.own-contexts: the index of the watched thread is its number and its selector.
       wire [3:0] watch_index = {watched, watch_select};
       core dut (.*);
       core_regfile regs (.*);
       wire [31:0] watch_pc = watch_pcs[watch_select];

       wire step = rst_n && commit && !commit_resume && commit_thread == watched;
       // core.reset-quiet: in reset, the state of the stages is still that of power-up.
       always_comb if (!rst_n) assert (!data_we && !we);
       // core.own-context: a write goes to the context of the index of its thread.
       always_comb if (we && commit_thread == watched) assert (wa[8:5] == watch_index);

       // Each commit equals one step of the instruction from its word, its program counter, its two
       // registers and its loaded word, by the units that the equiv checks prove.
       wire [31:0] insn, imm, alu_y, product, loaded;
       wire bad, wide, lui, auipc, jal, jalr, branch, load, store, opimm, op, mul, div, ecall, illegal, alt;
       wire taken, fault;
       wire [2:0] f3 = insn[14:12];
       core_expand expand (.word(commit_word), .insn, .illegal(bad), .wide);
       core_decode decode (.insn, .lui, .auipc, .jal, .jalr, .branch, .load, .store, .opimm, .op, .mul, .div,
                           .ecall, .illegal, .alt);
       core_imm immediate (.insn, .imm);
       wire [31:0] addr = commit_a + imm, link = commit_pc + (wide ? 32'd4 : 32'd2);
       core_alu alu (.f3, .alt, .a(commit_a), .b(opimm ? imm : commit_b), .y(alu_y));
       core_branch compare (.f3, .a(commit_a), .b(commit_b), .taken);
       core_misaligned align (.size(f3[1:0]), .lo(addr[1:0]), .fault);
       core_mul multiply (.f3(f3[1:0]), .a(commit_a), .b(commit_b), .y(product));
       core_load extract (.f3, .lo(addr[1:0]), .word(commit_load), .y(loaded));
       wire fetch_out, data_out;
       core_region fetch_region (.offset(commit_pc), .size(wide ? 3'd4 : 3'd2), .bound(watch_bound), .out(fetch_out));
       core_region data_region (.offset(addr), .size(3'd1 << f3[1:0]), .bound(watch_bound), .out(data_out));
       wire [1:0] cause = fetch_out ? 2'd2 : ecall ? 2'd1 : bad || illegal ? 2'd2
                        : (load || store) && (fault || data_out) ? 2'd2 : 2'd0;
       wire [31:0] next = jal || branch && taken ? commit_pc + imm : jalr ? {addr[31:1], 1'b0} : link;
       wire writes = lui || auipc || jal || jalr || load || opimm || op || mul;
       wire [31:0] value = lui ? imm : auipc ? commit_pc + imm : jal || jalr ? link : load ? loaded
                         : mul ? product : alu_y;
       wire done = step && cause == 2'd0;
       always_comb if (step) assert (commit_cause == cause);
       always_comb if (done) assert (commit_next == next && we == writes);
       always_comb if (done && writes) assert (wa[4:0] == insn[11:7]);
       // The solver cannot compare two multipliers across the registers of the pipeline. So the proof
       // checks that the multiplier reads the operands of the thread, and the equiv of core.mul proves it.
       always_comb if (done && writes && !mul) assert (wd == value);
       always_comb if (done && (load || store)) assert (commit_addr == addr);

       // core.own-state, core.issue, core.depth, core.index-write, core.div-wait: a model that names
       // only the turn, the writes of the port to the watched thread, its divide requests and its
       // commits gives its next state, and when it starts each instruction and commits it, 7 cycles
       // later. A divide takes 32 steps, and the thread resumes in its first slot after the last.
       wire mine = commit && commit_thread == watched, slot = 3'(turn + 3'd1) == watched;
       wire asked;
       logic [1:0][31:0] m_pcs;
       logic [31:0] set_data;
       logic [1:0] set_field;
       logic set_now, modelled = 1'b0;
       logic [5:0] m_steps;
       logic m_select, set_select;
       logic [73:0] model;
       // The thread waits while its divide runs, and its divider is ready once the steps are done.
       wire waiting = watch_state[2:1] == 2'b01, ready = watch_steps == 6'd0;
       wire [2:0] after;
       // A word store of thread 0 to the control block of the watched thread lands a cycle later. Thread 0
       // takes no store to its own word, and a running thread none to its selector or selected context.
       wire put_hit;
       wire [3:0] put_index;
       wire [1:0] put_field;
       core_control put_decode (.addr({16'd0, data_addr[15:2]}), .hit(put_hit), .index(put_index), .field(put_field));
       wire word = set_now && set_field == 2'd3 && watched != 3'd0, suspended = watch_state[2];
       core_state_next change (.state(watch_state), .commit(mine && !commit_resume), .why(commit_cause), .slot,
                               .ask(word && !set_data[0]), .start(asked), .done(slot && waiting && ready),
                               .write(word && suspended), .run(set_data[0]), .after);
       always_comb begin
           {m_pcs, m_steps, m_select} = {watch_pcs, watch_steps, watch_select};
           if (mine && !commit_resume && commit_cause == 2'd0) m_pcs[watch_select] = commit_next;
           if (asked) m_steps = 6'd32;
           else if (m_steps != 6'd0) m_steps = m_steps - 6'd1;
           if (word && suspended) m_select = set_data[4];
           if (set_now && set_field == 2'd0 && (set_select != watch_select || suspended)) m_pcs[set_select] = set_data;
       end
       // The turn gives the stage of the instruction of the watched thread, so that the stage cannot
       // disagree with the rotation: started[k] holds k + 1 cycles after the fetch.
       logic live = 1'b0;
       wire [2:0] phase = 3'(turn - watched);
       wire [6:0] started = live && phase != 3'd0 ? 7'(7'd1 << (phase - 3'd1)) : 7'd0;
       always_ff @(posedge clk) begin
           {set_now, set_field, set_select, set_data}
               <= {data_we && data_addr[16] && data_be == 4'hf && put_hit && put_index[3:1] == watched, put_field,
                   put_index[0], data_wdata};
           {modelled, model} <= {1'b1, rst_n ? {m_pcs, after, m_steps, m_select}
                                             : {64'd0, watched == 3'd0 ? 3'd0 : 3'd4, 6'd0, 1'b0}};
           if (!rst_n || turn == watched) live <= rst_n && watch_state[2:1] == 2'b00;
       end
       always_comb if (modelled) assert ({watch_pcs, watch_state, watch_steps, watch_select} == model);
       always_comb if (rst_n) assert ((mine && !commit_resume) == started[6]);
       always_comb if (rst_n) assert ((mine && commit_resume) == (slot && waiting && ready));
       // A resume writes the result that the divider of the thread holds.
       always_comb if (rst_n) assert (!(mine && commit_resume) || wd == watch_result);
       // core.div-time: since counts the cycles from the stage E of a divide, and ties the wait to the
       // steps and the turn. The thread skips no more turns than the twin, and all of them by its resume.
       wire [2:0] turns;
       core_div_time wait_time (.turns);
       logic [5:0] since;
       always_ff @(posedge clk) since <= asked ? 6'd1 : since + 6'd1;
       always_comb assert (waiting || watch_steps == 6'd0 || !rst_n);
       wire [5:0] skipped = (since + 6'd4) / 6'(bcw_params::CORE_THREADS);
       always_comb if (rst_n && waiting)
           assert (watch_steps == (since < 6'd33 ? 6'd33 - since : 6'd0) && turn == 3'(watched + 3'd4 + 3'(since))
                   && skipped <= 6'(turns) && (!(slot && ready) || skipped == 6'(turns)));

       // core.step: each commit carries the program counter of its turn, the word that arrived for it,
       // the addresses of its reads, the registers that came back, the address of its access and its
       // loaded word, each from the cycle of its stage.
       logic [31:0] pc_at, word_at, a_at, b_at, load_at;
       logic [16:0] addr_at;
       logic [8:0] ra_at, rb_at;
       // A divide of the watched thread asks the divider for its result in the stage E.
       wire [31:0] ask_insn;
       wire ask_div, ask_wide, ask_out;
       core_expand ask_expand (.word(word_at), .insn(ask_insn), .illegal(), .wide(ask_wide));
       core_region ask_region (.offset(pc_at), .size(ask_wide ? 3'd4 : 3'd2), .bound(watch_bound), .out(ask_out));
       core_decode ask_decode (.insn(ask_insn), .lui(), .auipc(), .jal(), .jalr(), .branch(), .load(), .store(),
                               .opimm(), .op(), .mul(), .div(ask_div), .ecall(), .illegal(), .alt());
       assign asked = started[3] && ask_div && !ask_out;
       always_ff @(posedge clk) begin
           if (turn == watched) pc_at <= watch_pc;
           if (started[0]) word_at <= fetch_word;
           if (started[1]) {ra_at, rb_at} <= {ra, rb};
           if (started[2]) {a_at, b_at} <= {a, b};
           if (started[4]) addr_at <= data_addr;
           if (started[5]) load_at <= data_rdata;
       end
       // core.regions: thread 0 has the supervisor part as its region.
       always_comb if (watched == 3'd0) assert (watch_base == 16'd0 && watch_bound == 17'(bcw_params::MEMORY_SUPERVISOR_PART));
       // core.address: the part is that of the thread, and the address is the base plus the offset.
       // core.size-word: the last word of the supervisor part, at its full address, reads as the size of
       // the worker part. A word of a control block is the word of another thread, which the test checks.
       wire load_hit;
       core_control load_decode (.addr(addr[31:2]), .hit(load_hit), .index(), .field());
       wire [31:0] loaded_at = watched == 3'd0 && load_hit ? commit_load
                             : watched == 3'd0 && addr[31:2] == 30'(bcw_params::MEMORY_SUPERVISOR_PART / 4 - 1)
                             ? 32'(bcw_params::MEMORY_WORKER_PART) : load_at;
       always_comb if (rst_n && turn == watched) assert (fetch_addr == {watched == 3'd0, 16'(watch_base + watch_pc[15:0])});
       // core.own-context: the reads, in the stage D, are in the context of the index of the thread.
       always_comb if (started[1])
           assert (ra[8:5] == watch_index && rb[8:5] == watch_index);
       always_comb if (started[4]) assert (mul_a == a_at && mul_b == b_at);
       always_comb if (started[6])
           assert ({commit_pc, commit_word, commit_a, commit_b, commit_load} == {pc_at, word_at, a_at, b_at, loaded_at}
                   && addr_at == {watched == 3'd0, 16'(watch_base + commit_addr[15:0])}
                   && ra_at[4:0] == insn[19:15] && rb_at[4:0] == insn[24:20]);
   endmodule

.. mutant:: build/rtl/core/core.v
   :kills: core.depth.prove

   -    wire [31:0] next = e_jal || e_branch && taken ? e_pc + e_imm : e_jalr ? {sum[31:1], 1'b0} : link;
   +    wire [31:0] next = e_jal || e_branch ? e_pc + e_imm : e_jalr ? {sum[31:1], 1'b0} : link;

.. mutant:: build/rtl/core/core.v
   :kills: core.depth.prove

   -    assign fetch_addr = {rot == '0, PW'(base[rot] + pc[rot][PW-1:0])};
   +    assign fetch_addr = {rot == '0, PW'(pc[rot][PW-1:0])};

.. mutant:: build/rtl/core/core.v
   :kills: core.depth.prove

   -    assign data_addr = {m1_t == '0, PW'(base[m1_t] + m1_addr[PW-1:0])};
   +    assign data_addr = {1'b0, PW'(base[m1_t] + m1_addr[PW-1:0])};

.. mutant:: build/rtl/core/core.v
   :kills: core.registers.test

   -           r_cause <= d_out ? REFUSED : ecall ? REQUEST : d_bad || illegal ? REFUSED : NONE;
   +           r_cause <= ecall ? REQUEST : d_bad || illegal ? REFUSED : NONE;

.. mutant:: build/rtl/core/core.v
   :kills: core.registers.test

   -    wire m2_size = m2_t == '0 && m2_addr[31:2] == 30'(bcw_params::MEMORY_SUPERVISOR_PART / 4 - 1);
   +    wire m2_size = m2_addr[31:2] == 30'(bcw_params::MEMORY_SUPERVISOR_PART / 4 - 1);

.. mutant:: build/rtl/core/core.v
   :kills: core.depth.prove

   -    assign we = rst_n && (retire && w_we_r || resume);
   +    assign we = retire && w_we_r || resume;

.. mutant:: build/rtl/core/core.v
   :kills: core.depth.prove

   -    assign wa = resume ? {index[rot_next], div_rd} : {index[w_t], w_rd};
   +    assign wa = resume ? {index[rot_next], div_rd} : {index[rot], w_rd};

.. mutant:: build/rtl/core/core.v
   :kills: core.depth.prove

   -    assign ra = {index[d_t], d_insn[19:15]};
   +    assign ra = {index[x_t], d_insn[19:15]};

.. mutant:: build/rtl/core/core.v
   :kills: core.depth.prove

   -    assign {mul_a, mul_b} = {m1_a, m1_b};
   +    assign {mul_a, mul_b} = {e_a, m1_b};

.. mutant:: build/rtl/core/core.v
   :kills: core.depth.prove

   -            <= {rst_n && r_v, r_t, r_pc, r_word, r_insn, r_imm, r_wide, r_alt, r_class, r_cause, a, b};
   +            <= {rst_n && r_v, r_t, r_pc, r_word, r_insn, r_imm, r_wide, r_alt, r_class, r_cause, b, a};

.. mutant:: build/rtl/core/core.v
   :kills: core.depth.prove

   -           core_thread #(.ID(t)) thread (.clk, .rst_n, .commit(w_v && w_t == t), .why(w_cause), .slot(rot_next == t),
   +           core_thread #(.ID(t)) thread (.clk, .rst_n, .commit(w_v), .why(w_cause), .slot(rot_next == t),

.. mutant:: build/rtl/core/core.v
   :kills: core.depth.prove

   -           {x_v, x_t, x_pc} <= {rst_n && fetching[rot], rot, pc[rot]};
   +           {x_v, x_t, x_pc} <= {rst_n && !waiting[rot], rot, pc[rot]};

.. mutant:: build/rtl/core/core.v
   :kills: core.registers.test

   -    assign resume = waiting[rot_next] && steps[rot_next] == 6'd0;
   +    assign resume = waiting[rot_next] && steps[rot_next] < 6'd9;

.. mutant:: build/rtl/core/core.v
   :kills: core.depth.prove

   -    assign resume = waiting[rot_next] && steps[rot_next] == 6'd0;
   +    assign resume = steps[rot_next] == 6'd0;

.. mutant:: build/rtl/core/core.v
   :kills: core.registers.test

   -                        .a(e_a), .b(e_b), .req_rd(e_insn[11:7]), .thread(rot_next), .look_thread(watch_thread),
   +                        .a(e_a), .b(e_b), .req_rd(e_insn[11:7]), .thread(rot), .look_thread(watch_thread),

.. rationale::

   An instruction ends before the next turn of its thread, with no forwarding or stall. The
   proof models a thread from only its turns, its commits and the stores of thread 0, so no other
   thread can change its timing.

Run state
=========

.. definition:: core.run-state
   :parent: core.thread

   The :dfn:`run state` of a thread is a number from 0 to 6. The core fetches for the thread in
   0 and 1, and the divide of the thread runs in 2 and 3. A stop is pending in 1 and 3. The run
   state is 4 after a stop, 5 after an ``ECALL`` and 6 after the core refuses an instruction.

.. requirement:: core.state-change
   :parent: design.auditability

   The core shall give each thread its next run state from its run state and the events of the
   cycle.

   .. twin::
      :stamp: e3520b72

      def core_state_next(state, commit, why, slot, ask, start, done, write, run):
          stop = 1 if state == 1 or state == 3 else 0
          asked = 1 if stop == 1 or ask == 1 else 0
          after = ((0 if run == 1 else state) if write == 1
                   else 4 + why if commit == 1 and why != 0
                   else 2 + asked if start == 1
                   else (4 if stop == 1 else ask) if done == 1
                   else 4 if slot == 1 and state == 1
                   else 1 if ask == 1 and state == 0
                   else 3 if ask == 1 and state == 2
                   else state)
          return {'after': after}

.. source:: build/rtl/core/core_state_next.v
   :implements: core.state-change

   module core_state_next (input wire [2:0] state, input wire commit, input wire [1:0] why,
                           input wire slot, ask, start, done, write, run, output logic [2:0] after);
       wire stop = state == 3'd1 || state == 3'd3;
       always_comb
           if (write) after = run ? 3'd0 : state;
           else if (commit && why != 2'd0) after = {1'b1, why};
           else if (start) after = {2'b01, stop || ask};
           else if (done) after = stop ? 3'd4 : {2'b00, ask};
           else if (slot && state == 3'd1) after = 3'd4;
           else if (ask && state == 3'd0) after = 3'd1;
           else if (ask && state == 3'd2) after = 3'd3;
           else after = state;
   endmodule

.. check:: equiv
   :verifies: core.state-change
   :module: core_state_next

.. rationale::

   One number holds the run state of a thread, and one function changes it. So a reader checks
   each change in one place, and the proof of the core checks each change against the function.

Suspension
==========

.. definition:: core.suspended
   :parent: core.run-state

   A :dfn:`suspended` thread has the run state 4, 5 or 6. The core fetches nothing in the turns
   of a suspended thread.

.. requirement:: core.suspend
   :parent: design.economy

   If an instruction is illegal or ``ECALL`` or has its access refused, then the core shall
   suspend its thread with its program counter on the instruction. The run state of the thread
   is then 5 after an ``ECALL``, and 6 after each other instruction.

.. requirement:: core.div-wait
   :parent: core.div

   While the divide of a thread runs, the core shall fetch nothing in the turns of the thread.

.. rationale::

   The supervisor handles each suspension. It moves the program counter past an ``ECALL`` that
   it accepts, and it can do an access that the core refused.

Control blocks
==============

.. definition:: core.control-block
   :parent: memory.supervisor

   The :dfn:`control block` of a thread is a set of words in the supervisor part: the word of the
   thread, which holds its selector and starts or stops it, and the program counter, base and bound
   of each of its contexts.

.. requirement:: core.control-map
   :parent: design.auditability

   The core shall place each control block at the end of the supervisor part.

   .. twin::
      :stamp: 8d5c0028

      def core_control(addr):
          top = MEMORY_SUPERVISOR_PART // 4
          contexts = 1 if addr // 64 == top // 64 - 2 and addr % 4 != 3 else 0
          threads = 1 if addr // 8 == top // 8 - 8 else 0
          return {'hit': 1 if contexts == 1 or threads == 1 else 0,
                  'index': addr // 4 % 16 if contexts == 1 else addr % 8 * 2,
                  'field': addr % 4 if contexts == 1 else 3}

.. source:: build/rtl/core/core_control.v
   :implements: core.control-map

   // The address is that of a word: its bits 1 and 0 name no word.
   module core_control (input wire [31:2] addr, output wire hit,
                        output wire [bcw_params::CORE_CONTEXT_WIDTH-1:0] index, output wire [1:0] field);
       localparam int CW = bcw_params::CORE_CONTEXT_WIDTH, TW = bcw_params::CORE_TURN_WIDTH;
       localparam int TOP = bcw_params::MEMORY_SUPERVISOR_PART;
       wire contexts = addr[31:8] == 24'(TOP / 256 - 2) && addr[3:2] != 2'd3;
       wire threads = addr[31:5] == 27'(TOP / 32 - 8);
       assign hit = contexts || threads;
       assign index = contexts ? addr[4 +: CW] : {addr[2 +: TW], bcw_params::CORE_SELECT_WIDTH'(0)};
       assign field = contexts ? addr[3:2] : 2'd3;
   endmodule

.. check:: equiv
   :verifies: core.control-map
   :module: core_control

.. requirement:: core.control-write
   :parent: design.auditability

   If a store of thread 0 reaches the word of thread 0 or the selector or context in use of a
   thread that is not suspended, then the core shall ignore the store.

.. requirement:: core.control-read
   :parent: design.auditability

   When thread 0 loads a word of a control block, the core shall give the value of the word.

Thread control
==============

.. requirement:: core.own-state
   :parent: design.timing-invariant

   The core shall change the state of a thread only for an instruction of the thread, or a store
   of thread 0 to its control block.

.. requirement:: core.index-write
   :parent: design.timing-invariant

   The core shall write a selector or a region only for a store of thread 0 to a control block.

.. source:: build/rtl/core/core_thread.v
   :implements: core.index-write, core.own-contexts, core.own-pc, core.stop, core.state-change,
                core.regions

   module core_thread #(parameter int ID = 0) (input wire clk, rst_n, commit, input wire [1:0] why,
                   input wire slot, start, done, input wire [31:0] next, input wire put,
                   input wire [bcw_params::CORE_SELECT_WIDTH-1:0] put_select, input wire [1:0] put_field,
                   input wire [31:0] put_data, output logic [bcw_params::CORE_THREAD_CONTEXTS-1:0][31:0] pcs,
                   output wire [bcw_params::CORE_THREAD_CONTEXTS-1:0][bcw_params::MEMORY_PART_WIDTH-1:0] bases,
                   output wire [bcw_params::CORE_THREAD_CONTEXTS-1:0][bcw_params::MEMORY_PART_WIDTH:0] bounds, output wire [31:0] pc,
                   output wire [bcw_params::MEMORY_PART_WIDTH-1:0] base, output wire [bcw_params::MEMORY_PART_WIDTH:0] bound,
                   output logic [2:0] state, output logic [bcw_params::CORE_SELECT_WIDTH-1:0] select,
                   output wire [bcw_params::CORE_CONTEXT_WIDTH-1:0] index);
       localparam int C = bcw_params::CORE_THREAD_CONTEXTS, PW = bcw_params::MEMORY_PART_WIDTH, SW = bcw_params::CORE_SELECT_WIDTH;
       localparam logic [PW:0] SUPERVISOR = (PW + 1)'(bcw_params::MEMORY_SUPERVISOR_PART);
       // A store to the word of a thread starts it or stops it; the word of thread 0 takes no store, so
       // the supervisor cannot stop itself.
       wire word = put && put_field == 2'd3 && ID != 0, run = put_data[0];
       wire [2:0] after;
       core_state_next change (.state, .commit, .why, .slot, .ask(word && !run), .start, .done,
                               .write(word && state[2]), .run, .after);
       assign index = {bcw_params::CORE_TURN_WIDTH'(ID), select};
       logic [C-1:0][PW-1:0] held_bases;
       logic [C-1:0][PW:0] held_bounds;
       // Thread 0 has the supervisor part as the region of each of its contexts, by wiring.
       assign bases = ID == 0 ? '0 : held_bases;
       assign bounds = ID == 0 ? {C{SUPERVISOR}} : held_bounds;
       assign {pc, base, bound} = {pcs[select], bases[select], bounds[select]};
       logic [C-1:0][31:0] after_pcs;
       logic [C-1:0][PW-1:0] after_bases;
       logic [C-1:0][PW:0] after_bounds;
       // A store reaches a context that the thread does not run, or any context of a suspended thread.
       always_comb
           for (int c = 0; c < C; c++) begin
               {after_pcs[c], after_bases[c], after_bounds[c]} = {pcs[c], held_bases[c], held_bounds[c]};
               if (commit && why == 2'd0 && select == SW'(c)) after_pcs[c] = next;
               if (put && put_select == SW'(c) && (select != SW'(c) || state[2]))
                   case (put_field)
                       2'd0: after_pcs[c] = put_data;
                       2'd1: after_bases[c] = put_data[PW-1:0];
                       2'd2: after_bounds[c] = put_data[PW:0];
                       default: ;
                   endcase
           end
       always_ff @(posedge clk)
           if (!rst_n) begin
               {pcs, held_bases, held_bounds} <= '0;
               {state, select} <= {ID == 0 ? 3'd0 : 3'd4, SW'(0)};
           end else begin
               {pcs, held_bases, held_bounds, state} <= {after_pcs, after_bases, after_bounds, after};
               if (word && state[2]) select <= put_data[4 +: SW];
           end
   endmodule

.. mutant:: build/rtl/core/core_thread.v
   :kills: core.registers.test

   -               if (word && state[2]) select <= put_data[4 +: SW];
   +               if (word) select <= put_data[4 +: SW];

.. mutant:: build/rtl/core/core_thread.v
   :kills: core.registers.test

   -    assign index = {bcw_params::CORE_TURN_WIDTH'(ID), select};
   +    assign index = bcw_params::CORE_CONTEXT_WIDTH'(select);

.. mutant:: build/rtl/core/core_thread.v
   :kills: core.depth.prove

   -               if (commit && why == 2'd0 && select == SW'(c)) after_pcs[c] = next;
   +               if (commit && select == SW'(c)) after_pcs[c] = next;

.. mutant:: build/rtl/core/core_thread.v
   :kills: core.depth.prove

   -               if (commit && why == 2'd0 && select == SW'(c)) after_pcs[c] = next;
   +               if (commit && why == 2'd0) after_pcs[c] = next;

.. mutant:: build/rtl/core/core_thread.v
   :kills: core.registers.test

   -               if (put && put_select == SW'(c) && (select != SW'(c) || state[2]))
   +               if (put && put_select == SW'(c))

.. mutant:: build/rtl/core/core_thread.v
   :kills: core.depth.prove

   -    wire word = put && put_field == 2'd3 && ID != 0, run = put_data[0];
   +    wire word = put && put_field == 2'd3, run = put_data[0];

.. mutant:: build/rtl/core/core_thread.v
   :kills: core.depth.prove, core.registers.test

   -    assign bounds = ID == 0 ? {C{SUPERVISOR}} : held_bounds;
   +    assign bounds = held_bounds;

.. rationale::

   Only thread 0 writes a selector, and the index of a thread holds the number of the thread. So
   no thread can name a context of another, and the supervisor cannot give it one.

Reset
=====

.. requirement:: core.reset
   :parent: design.economy

   When the core leaves reset, the core shall run thread 0 from address 0, and hold each other
   thread suspended.

.. requirement:: core.reset-quiet
   :parent: design.auditability

   While the core is in reset, the core shall write no register and no memory.

Stop
====

.. requirement:: core.stop
   :parent: design.timing-invariant

   When thread 0 stops a thread in its word, the core shall suspend the thread before the first of
   its turns
   in which no divide holds it, with its program counter on the instruction of that turn.

.. rationale::

   A stop takes effect between two instructions and after a divide, so the thread resumes as if
   it had not stopped. The run state 4 tells the supervisor that the stop came from thread 0.

.. check:: test
   :verifies: core.registers, core.own-context, core.step, core.suspend, core.div, core.div-wait,
              core.control-write, core.control-read, core.reset, core.stop, core.own-pc, core.region-check,
              core.size-word

   module tb_core;
       logic clk = 0, rst_n = 0;
       logic [16:0] fetch_addr, data_addr;
       logic [31:0] fetch_word, data_wdata, data_rdata;
       logic [3:0] data_be;
       logic data_we;
       logic [1:0][31:0] watch_pcs;
       logic [15:0] watch_base;
       logic [16:0] watch_bound;
       logic watch_select;
       wire [31:0] watch_pc = watch_pcs[watch_select];
       logic [2:0] watch_thread = 0, watch_state;
       logic [5:0] watch_steps;
       logic [31:0] watch_result;
       wire [2:0] turn, commit_thread;
       wire commit, commit_resume, we;
       wire [1:0] commit_cause;
       wire [8:0] ra, rb, wa;
       wire [31:0] wd, a, b, commit_pc, commit_word, commit_a, commit_b, commit_addr, commit_load, commit_next;
       wire [31:0] mul_a, mul_b;
       core dut (.*);
       core_regfile regs (.*);

       // The worker part, then the supervisor part at 17'h10000.
       logic [7:0] mem [131072];
       always @(posedge clk) begin
           fetch_word <= {mem[17'(fetch_addr + 3)], mem[17'(fetch_addr + 2)], mem[17'(fetch_addr + 1)],
                          mem[17'(fetch_addr)]};
           data_rdata <= {mem[{data_addr[16:2], 2'd3}], mem[{data_addr[16:2], 2'd2}],
                          mem[{data_addr[16:2], 2'd1}], mem[{data_addr[16:2], 2'd0}]};
           if (data_we)
               for (int i = 0; i < 4; i++)
                   if (data_be[i]) mem[{data_addr[16:2], 2'(i)}] <= data_wdata[8 * i +: 8];
       end
       always #5 clk = !clk;

       // A program goes at its offset at in the region that starts at the physical address region.
       int at, region;
       task automatic put(input [31:0] word);
           {mem[17'(region + at + 3)], mem[17'(region + at + 2)], mem[17'(region + at + 1)],
            mem[17'(region + at)]} = word;
           at += 4;
       endtask
       task automatic put16(input [15:0] half);
           {mem[17'(region + at + 1)], mem[17'(region + at)]} = half;
           at += 2;
       endtask
       task automatic li(input [4:0] rd, input [31:0] value);
           logic [31:0] upper = (value + 32'h800) >> 12;
           put({upper[19:0], rd, 7'd55});
           put(rv32::enc_i(12'(value - (upper << 12)), rd, 3'd0, rd, 7'd19));
       endtask
       // Stores register rs at the next word of the results of the thread, and records what it should be.
       int out;
       logic [31:0] want [int];
       task automatic keep(input [4:0] rs, input [31:0] value);
           li(5'd31, 32'(out));
           put(rv32::enc_s(12'd0, rs, 5'd31, 3'd2, 7'd35));
           want[region + out] = value;
           out += 4;
       endtask
       function automatic [31:0] word_at(input int a);
           return {mem[17'(a + 3)], mem[17'(a + 2)], mem[17'(a + 1)], mem[17'(a)]};
       endfunction

       localparam logic [31:0] ECALL = 32'h73;
       logic [31:0] ops [$] = '{0, 1, 2, 7, 32'hffffffff, 32'h80000000, 32'h7fffffff, 32'h12345678, 32'hfffffff9,
                                 32'hdeadbeef};
       int fails = 0;

       // Thread 0: every class of instruction but the divide, then ECALL.
       task automatic program0();
           int here;
           li(5'd1, 32'h12345678); li(5'd2, 32'hfffffff9);
           put(rv32::enc_r(7'd0, 5'd2, 5'd1, 3'd0, 5'd3, 7'd51));  keep(5'd3, 32'h12345678 + 32'hfffffff9);
           put(rv32::enc_r(7'd32, 5'd2, 5'd1, 3'd0, 5'd3, 7'd51)); keep(5'd3, 32'h12345678 - 32'hfffffff9);
           put(rv32::enc_r(7'd0, 5'd2, 5'd1, 3'd1, 5'd3, 7'd51));  keep(5'd3, 32'h12345678 << 25);
           put(rv32::enc_r(7'd0, 5'd2, 5'd1, 3'd2, 5'd3, 7'd51));  keep(5'd3, 0);
           put(rv32::enc_r(7'd0, 5'd2, 5'd1, 3'd3, 5'd3, 7'd51));  keep(5'd3, 1);
           put(rv32::enc_r(7'd32, 5'd1, 5'd2, 3'd5, 5'd3, 7'd51)); keep(5'd3, 32'hffffffff);
           put(rv32::enc_i(12'd4, 5'd2, 3'd5, 5'd3, 7'd19));       keep(5'd3, 32'h0fffffff);
           put(rv32::enc_i({7'd32, 5'd4}, 5'd2, 3'd5, 5'd3, 7'd19)); keep(5'd3, 32'hffffffff);
           put(rv32::enc_i(12'hff0, 5'd1, 3'd7, 5'd3, 7'd19));     keep(5'd3, 32'h12345670);
           put(rv32::enc_r(7'd1, 5'd2, 5'd1, 3'd0, 5'd3, 7'd51));  keep(5'd3, 32'h12345678 * 32'hfffffff9);
           put(rv32::enc_r(7'd1, 5'd2, 5'd1, 3'd1, 5'd3, 7'd51));  keep(5'd3, 32'hffffffff);
           put(rv32::enc_r(7'd1, 5'd2, 5'd1, 3'd3, 5'd3, 7'd51));  keep(5'd3, 32'h12345677);
           // Store a byte and a half, and load them back signed and unsigned.
           li(5'd4, 32'h3800);
           put(rv32::enc_s(12'd1, 5'd2, 5'd4, 3'd0, 7'd35));
           put(rv32::enc_s(12'd2, 5'd2, 5'd4, 3'd1, 7'd35));
           put(rv32::enc_i(12'd1, 5'd4, 3'd0, 5'd3, 7'd3));        keep(5'd3, 32'hfffffff9);
           put(rv32::enc_i(12'd1, 5'd4, 3'd4, 5'd3, 7'd3));        keep(5'd3, 32'h000000f9);
           put(rv32::enc_i(12'd2, 5'd4, 3'd1, 5'd3, 7'd3));        keep(5'd3, 32'hfffffff9);
           put(rv32::enc_i(12'd2, 5'd4, 3'd5, 5'd3, 7'd3));        keep(5'd3, 32'h0000fff9);
           // A taken branch skips an addi; a not-taken one does not.
           li(5'd3, 0);
           put(rv32::enc_b(12'd4, 5'd2, 5'd1, 3'd1, 7'd99));
           put(rv32::enc_i(12'd1, 5'd3, 3'd0, 5'd3, 7'd19));
           put(rv32::enc_b(12'd4, 5'd2, 5'd1, 3'd0, 7'd99));
           put(rv32::enc_i(12'd2, 5'd3, 3'd0, 5'd3, 7'd19));       keep(5'd3, 2);
           // jal links and jumps; auipc; compressed c.li x5, 7 and c.addi x5, 1.
           here = at;
           put(rv32::enc_j(20'd4, 5'd6, 7'd111));
           put(rv32::enc_i(12'd1, 5'd3, 3'd0, 5'd3, 7'd19));
           put(rv32::enc_i(12'd0, 5'd6, 3'd0, 5'd7, 7'd19));       keep(5'd7, 32'(here + 4));
           here = at;
           put({20'd1, 5'd8, 7'd23});                        keep(5'd8, 32'(here + 32'h1000));
           put16(16'h429d); put16(16'h0285);                 keep(5'd5, 8);
           put(rv32::enc_i(12'd5, 5'd1, 3'd0, 5'd0, 7'd19));
           put(rv32::enc_i(12'd0, 5'd0, 3'd0, 5'd3, 7'd19));       keep(5'd3, 0);
           // The last word of the supervisor part reads as the size of the worker part.
           li(5'd9, 32'h3ffc);
           put(rv32::enc_i(12'd0, 5'd9, 3'd2, 5'd3, 7'd3));        keep(5'd3, 32'h10000);
           put(ECALL);
       endtask

       task automatic divides(input [31:0] x, y);
           li(5'd1, x); li(5'd2, y);
           for (int f = 4; f < 8; f++) begin
               put(rv32::enc_r(7'd1, 5'd2, 5'd1, 3'(f), 5'd3, 7'd51));
               keep(5'd3, expect_div(f, x, y));
           end
       endtask

       // Thread 1: each divide and remainder of every pair of ops and of 100 random pairs, then ECALL.
       task automatic program1();
           region = 0; at = 0; out = 32'h4000;
           foreach (ops[i]) foreach (ops[j]) divides(ops[i], ops[j]);
           for (int k = 0; k < 100; k++) divides($urandom, k % 3 == 0 ? $urandom % 97 : $urandom);
           // A worker that loads at the offset of the size word reads its own memory.
           li(5'd9, 32'h3ffc);
           put(rv32::enc_i(12'd0, 5'd9, 3'd2, 5'd3, 7'd3));        keep(5'd3, 32'd0);
           put(ECALL);
       endtask

       function automatic [31:0] expect_div(input int f, input [31:0] a, b);
           case (f)
               4: return b == 0 ? 32'hffffffff : a == 32'h80000000 && b == 32'hffffffff ? a
                       : 32'($signed(a) / $signed(b));
               5: return b == 0 ? 32'hffffffff : a / b;
               6: return b == 0 ? a : a == 32'h80000000 && b == 32'hffffffff ? 0 : 32'($signed(a) % $signed(b));
               default: return b == 0 ? a : a % b;
           endcase
       endfunction

       // The port starts a thread in a context, and sets the program counter of the context if pc_we.
       // The port starts a thread in a context, and sets the program counter and region of the context
       // if context_we.
       // Thread 0, the supervisor, stores a word to a control block, sets the program counter and region
       // of a context, writes the selector and the run bit of a thread, and waits for a run state.
       localparam int CONTEXTS = 32'h3e00, THREADS = 32'h3f00;
       task automatic poke(input [31:0] addr, input [31:0] value);
           li(5'd29, value); li(5'd30, addr);
           put(rv32::enc_s(12'd0, 5'd29, 5'd30, 3'd2, 7'd35));
       endtask
       task automatic set_context(input [3:0] index, input [31:0] pc, base, bound);
           poke(CONTEXTS + 16 * index, pc); poke(CONTEXTS + 16 * index + 4, base); poke(CONTEXTS + 16 * index + 8, bound);
       endtask
       task automatic control(input [2:0] t, input select, input run);
           poke(THREADS + 4 * t, {27'd0, select, 3'd0, run});
       endtask
       // Thread 0 loads the word of thread t into x29 until its bits in mask are value.
       task automatic await(input [2:0] t, input [31:0] mask, input [31:0] value);
           int here;
           li(5'd30, THREADS + 4 * t); li(5'd28, mask); li(5'd27, value);
           here = at;
           put(rv32::enc_i(12'd0, 5'd30, 3'd2, 5'd29, 7'd3));
           put(rv32::enc_r(7'd0, 5'd28, 5'd29, 3'd7, 5'd29, 7'd51));
           put(rv32::enc_b(12'((here - at) / 2), 5'd27, 5'd29, 3'd1, 7'd99));
       endtask

       // The supervisor sets the regions and starts the workers. A store to the selector or the bound of
       // running thread 1 has no effect; one to context 8, which thread 4 does not select, has.
       // Then it stops thread 6 at pseudo-random points and starts it again, until thread 6 requests.
       // Last, it stops thread 4 in its loop, runs context 8 to its ECALL, and selects 9 again.
       task automatic supervisor();
           int loop, check;
           set_context(4'd2, 0, 32'h0000, 32'h5000); set_context(4'd4, 0, 32'h5000, 32'h4000);
           set_context(4'd6, 0, 32'h5100, 32'h100); set_context(4'd9, 0, 32'h5200, 32'h200);
           set_context(4'd10, 0, 32'h5600, 32'h100); set_context(4'd12, 0, 32'h5800, 32'h800);
           set_context(4'd14, 0, 32'h5700, 32'h10);
           control(3'd1, 1'b0, 1'b1); control(3'd2, 1'b0, 1'b1); control(3'd3, 1'b0, 1'b1);
           control(3'd4, 1'b1, 1'b1); control(3'd5, 1'b0, 1'b1); control(3'd7, 1'b0, 1'b1);
           control(3'd6, 1'b0, 1'b1);
           control(3'd1, 1'b1, 1'b1); poke(CONTEXTS + 16 * 2 + 8, 32'd0);
           set_context(4'd8, 0, 32'h5400, 32'h200);
           li(5'd20, 32'h1234567); li(5'd21, 20); li(5'd23, 1103515245); li(5'd24, 12345);
           loop = at;
           put(rv32::enc_r(7'd1, 5'd23, 5'd20, 3'd0, 5'd20, 7'd51));
           put(rv32::enc_r(7'd0, 5'd24, 5'd20, 3'd0, 5'd20, 7'd51));
           put(rv32::enc_i({7'd0, 5'd28}, 5'd20, 3'd5, 5'd22, 7'd19));
           put(rv32::enc_i(12'hfff, 5'd22, 3'd0, 5'd22, 7'd19));
           put(rv32::enc_b(12'hffe, 5'd0, 5'd22, 3'd5, 7'd99));
           control(3'd6, 1'b0, 1'b0);
           await(3'd6, 32'd4, 32'd4);
           put(rv32::enc_i(12'd0, 5'd30, 3'd2, 5'd29, 7'd3));
           put(rv32::enc_i(12'd7, 5'd29, 3'd7, 5'd29, 7'd19));
           li(5'd27, 32'd5);
           check = at; put(32'd0);
           control(3'd6, 1'b0, 1'b1);
           put(rv32::enc_i(12'hfff, 5'd21, 3'd0, 5'd21, 7'd19));
           put(rv32::enc_b(12'((loop - at) / 2), 5'd0, 5'd21, 3'd1, 7'd99));
           begin
               int done = at;
               at = check; put(rv32::enc_b(12'((done - check) / 2), 5'd27, 5'd29, 3'd0, 7'd99)); at = done;
           end
           control(3'd4, 1'b1, 1'b0);
           await(3'd4, 32'd7, 32'd4);
           control(3'd4, 1'b0, 1'b1);
           await(3'd4, 32'd7, 32'd5);
           control(3'd4, 1'b1, 1'b1);
           // Thread 4 runs its loop again, in context 9.
           li(5'd30, THREADS + 16);
           put(rv32::enc_i(12'd0, 5'd30, 3'd2, 5'd29, 7'd3));
           put(rv32::enc_i(12'h1f, 5'd29, 3'd7, 5'd29, 7'd19));   keep(5'd29, 32'h10);
       endtask

       // The states that a thread can end in: stopped, requesting and refused.
       localparam logic [2:0] STOPPED = 3'd4, REQUESTING = 3'd5, REFUSED = 3'd6;
       task automatic expect_stop(input [2:0] t, input [2:0] state, input [31:0] pc);
           watch_thread = t;
           #1;
           if (watch_state != state || watch_pc != pc) begin
               $display("FAIL: thread %0d state=%0d pc=%h, want state %0d at pc %h", t, watch_state,
                        watch_pc, state, pc);
               fails++;
           end
       endtask

       int ecall0, ecall1, ecall4, ecall8, ecall6, refused5;
       initial begin
           foreach (mem[i]) mem[i] = 0;
           region = 32'h10000; at = 0; out = 32'h3000;
           supervisor(); program0(); ecall0 = at - 4;
           program1(); ecall1 = at - 4;
           if (at > 32'h4000) $fatal(1, "the code of thread 1 reaches its results");
           // Thread 2 stores to the control block of context 5, which reaches only its own memory, then meets
           // an illegal instruction; thread 3 a misaligned load.
           region = 32'h5000; at = 0; li(5'd5, 32'd4); li(5'd6, 32'h3e50);
           put(rv32::enc_s(12'd0, 5'd5, 5'd6, 3'd2, 7'd35)); put(32'hffffffff);
           region = 32'h5100; at = 0; put(rv32::enc_i(12'd2, 5'd0, 3'd2, 5'd3, 7'd3));
           // Thread 4 counts down in its second context, 9, until the supervisor stops it and runs its first
           // context, 8, which writes the same register. Then the supervisor selects 9 again with no
           // program counter, and 9 counts on with its own register.
           region = 32'h5200; at = 0; li(5'd5, 32'd42); li(5'd6, 32'd5000);
           put(rv32::enc_i(12'hfff, 5'd6, 3'd0, 5'd6, 7'd19));
           put(rv32::enc_b(12'hffe, 5'd0, 5'd6, 3'd1, 7'd99));
           out = 32'h100; keep(5'd5, 32'd42); keep(5'd6, 32'd0); put(ECALL); ecall4 = at - 4;
           region = 32'h5400; at = 0; out = 32'h100; li(5'd5, 32'd7); keep(5'd5, 32'd7); put(ECALL); ecall8 = at - 4;
           // Thread 5 loads the last word of its region, then the word past it.
           region = 32'h5600; at = 0; li(5'd9, 32'hfc);
           put(rv32::enc_i(12'd0, 5'd9, 3'd2, 5'd3, 7'd3));
           refused5 = at; put(rv32::enc_i(12'd4, 5'd9, 3'd2, 5'd3, 7'd3));
           // Thread 7 runs to the end of its region, where a wide instruction would reach past its bound.
           region = 32'h5700; at = 0; put16(16'h0001);
           repeat (3) put(rv32::enc_i(12'd0, 5'd0, 3'd0, 5'd0, 7'd19));
           put(rv32::enc_i(12'd0, 5'd0, 3'd0, 5'd0, 7'd19));
           // Thread 6 divides 16 times while the supervisor stops it at random points: its results must be
           // those of a run with no stop.
           region = 32'h5800; at = 0; out = 32'h400; li(5'd5, 32'd1000); li(5'd6, 32'd7);
           for (int k = 0; k < 16; k++) begin
               put(rv32::enc_r(7'd1, 5'd6, 5'd5, 3'd5, 5'd7, 7'd51));
               keep(5'd7, 32'(1000 / (7 + k)));
               put(rv32::enc_i(12'd1, 5'd6, 3'd0, 5'd6, 7'd19));
           end
           put(ECALL); ecall6 = at - 4;
           repeat (4) @(negedge clk);
           rst_n = 1;
           repeat (20) @(negedge clk);
           for (int t = 1; t < 8; t++) expect_stop(3'(t), STOPPED, 32'd0);
           repeat (400000) @(negedge clk);
           expect_stop(3'd0, REQUESTING, 32'(ecall0));
           expect_stop(3'd1, REQUESTING, 32'(ecall1));
           if (watch_select) begin $display("FAIL: thread 1 took a selector while it ran"); fails++; end
           expect_stop(3'd2, REFUSED, 32'h14);
           if (watch_pcs[1] != 0) begin $display("FAIL: a worker wrote a control block"); fails++; end
           expect_stop(3'd3, REFUSED, 32'd0);
           expect_stop(3'd4, REQUESTING, 32'(ecall4));
           if (!watch_select) begin $display("FAIL: thread 4 left its second context"); fails++; end
           expect_stop(3'd5, REFUSED, 32'(refused5));
           expect_stop(3'd6, REQUESTING, 32'(ecall6));
           expect_stop(3'd7, REFUSED, 32'he);
           foreach (want[a]) if (word_at(a) != want[a]) begin
               if (fails < 20) $display("FAIL: word %h is %h, want %h", a, word_at(a), want[a]);
               fails++;
           end
           $display("%0d results, %0d failures", want.size(), fails);
           if (fails != 0) $fatal(1, "the core failed");
           $finish;
       end
   endmodule

.. mutant:: build/rtl/core/core_regfile.v
   :kills: core.registers.test

   -    assign a = zero_a ? 32'd0 : read_a;
   +    assign a = read_a;

.. mutant:: build/rtl/core/core.v
   :kills: core.registers.test

   -           {q_we, q_index, q_field, q_data} <= {rst_n && m1_v && m1_store && m1_cause == NONE && m1_t == '0 && m1_hit
   +           {q_we, q_index, q_field, q_data} <= {rst_n && m1_v && m1_store && m1_cause == NONE && m1_hit

.. mutant:: build/rtl/core/core.v
   :kills: core.registers.test

   -                           : 32'({select[m1_thread], 1'b0, state[m1_thread]});
   +                           : 32'(state[m1_thread]);

.. mutant:: build/rtl/core/core_thread.v
   :kills: core.registers.test

   -                {state, select} <= {ID == 0 ? 3'd0 : 3'd4, SW'(0)};
   +                {state, select} <= {3'd0, SW'(0)};
