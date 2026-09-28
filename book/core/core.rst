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

   The width of the index of a thread.

.. parameter:: core.clock
   :parent: core.core
   :value: 80 * 10 ** 6
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
       <<:core.rv32-formats>>
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
               3'b000: if (c[12:5] == 8'b0) illegal = 1'b1;                   // reserved
                       else insn = enc_i(imm_addi4spn, 5'd2, 3'b000, rdp, OP_IMM);
               3'b010: insn = enc_i(imm_lwsw, r1p, 3'b010, rdp, OP_LOAD);    // c.lw
               3'b110: insn = enc_s(imm_lwsw, rdp, r1p, 3'b010, OP_STORE);   // c.sw
               default: illegal = 1'b1;                                     // F, D, reserved
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
       <<:core.rv32-formats>>
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
               3'b000: insn = enc_i(imm_ci, rd_full, 3'b000, rd_full, OP_IMM);      // c.addi
               3'b001: insn = enc_j(imm_cj, 5'd1, OP_JAL);                          // c.jal
               3'b010: insn = enc_i(imm_ci, 5'd0, 3'b000, rd_full, OP_IMM);         // c.li
               3'b011: if ({c[12], c[6:2]} == 6'b0) illegal = 1'b1;                 // reserved
                       else if (rd_full == 5'd2)                                    // c.addi16sp
                           insn = enc_i(imm_addi16sp, 5'd2, 3'b000, 5'd2, OP_IMM);
                       else insn = {{15{c[12]}}, c[6:2], rd_full, OP_LUI};          // c.lui
               3'b100: case (c[11:10])
                   2'b00: if (c[12]) illegal = 1'b1;                                // c.srli
                          else insn = enc_i({6'b0, shamt}, r1p, 3'b101, r1p, OP_IMM);
                   2'b01: if (c[12]) illegal = 1'b1;                                // c.srai
                          else insn = enc_i({6'b010000, shamt}, r1p, 3'b101, r1p, OP_IMM);
                   2'b10: insn = enc_i(imm_ci, r1p, 3'b111, r1p, OP_IMM);           // c.andi
                   2'b11: if (c[12]) illegal = 1'b1;                                // RV64 only
                          else case (c[6:5])
                       2'b00: insn = enc_r(7'b0100000, rdp, r1p, 3'b000, r1p, OP_REG);  // sub
                       2'b01: insn = enc_r(7'b0000000, rdp, r1p, 3'b100, r1p, OP_REG);  // xor
                       2'b10: insn = enc_r(7'b0000000, rdp, r1p, 3'b110, r1p, OP_REG);  // or
                       2'b11: insn = enc_r(7'b0000000, rdp, r1p, 3'b111, r1p, OP_REG);  // and
                   endcase
               endcase
               3'b101: insn = enc_j(imm_cj, 5'd0, OP_JAL);                          // c.j
               3'b110: insn = enc_b(imm_cb, 5'd0, r1p, 3'b000, OP_BR);              // c.beqz
               3'b111: insn = enc_b(imm_cb, 5'd0, r1p, 3'b001, OP_BR);              // c.bnez
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
       <<:core.rv32-formats>>
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
               3'b000: if (c[12]) illegal = 1'b1;                                   // RV32: shamt[5]
                       else insn = enc_i({6'b0, shamt}, rd_full, 3'b001, rd_full, OP_IMM);
               3'b010: if (rd_full == 5'd0) illegal = 1'b1;                         // c.lwsp
                       else insn = enc_i(imm_lwsp, 5'd2, 3'b010, rd_full, OP_LOAD);
               3'b100: if (!c[12] && rs2_full == 5'd0 && rd_full == 5'd0)
                           illegal = 1'b1;                                          // reserved
                       else if (!c[12] && rs2_full == 5'd0)                         // c.jr
                           insn = enc_i(12'b0, rd_full, 3'b000, 5'd0, OP_JALR);
                       else if (!c[12])                                             // c.mv
                           insn = enc_r(7'b0, rs2_full, 5'd0, 3'b000, rd_full, OP_REG);
                       else if (rs2_full == 5'd0 && rd_full == 5'd0)
                           insn = 32'h00100073;                                     // c.ebreak
                       else if (rs2_full == 5'd0)                                   // c.jalr
                           insn = enc_i(12'b0, rd_full, 3'b000, 5'd1, OP_JALR);
                       else insn = enc_r(7'b0, rs2_full, rd_full, 3'b000, rd_full, OP_REG); // c.add
               3'b110: insn = enc_s(imm_swsp, rs2_full, 5'd2, 3'b010, OP_STORE);    // c.swsp
               default: illegal = 1'b1;                                             // F, D
           endcase
           if (illegal) insn = 32'h00000013;
       end
   endmodule

.. check:: equiv
   :verifies: core.rvc2
   :module: core_rvc2

.. source:: :core.rv32-formats

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

.. rationale::

   A stock instruction set adds no concept and brings a toolchain that works. The ``C``
   extension makes code smaller, which eases the pressure on the memory pool.

Decode
======

.. requirement:: core.decode
   :parent: design.economy

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

   The decoder checks every field, not the opcode alone. An encoding outside ``RV32IM`` then
   suspends its thread, and never runs as another instruction.

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

   The core shall give the result of each divide 32 cycles after its request, for any operands
   and any work of the other threads.

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

.. source:: build/rtl/core/core_div.v
   :implements: core.div, core.div-time

   module core_div (input wire clk, rst_n, req, input wire [bcw_params::CORE_TURN_WIDTH-1:0] req_thread,
                    input wire [1:0] f3, input wire [31:0] a, b, input wire [4:0] req_rd,
                    input wire [bcw_params::CORE_TURN_WIDTH-1:0] thread,
                    output wire done, output wire [31:0] result, output wire [4:0] rd);
       localparam int T = bcw_params::CORE_THREADS;
       logic [31:0] r [T], q [T], d [T];
       logic [5:0] count [T];
       logic negate [T], remainder [T];
       logic [4:0] dest [T];
       wire [31:0] r_next [T], q_next [T];
       wire sa = !f3[0] && a[31], sb = !f3[0] && b[31];
       for (genvar t = 0; t < T; t++) begin : step
           core_div_step unit (.r(r[t]), .q(q[t]), .d(d[t]), .r_next(r_next[t]), .q_next(q_next[t]));
           always_ff @(posedge clk)
               if (!rst_n) count[t] <= '0;
               else if (req && req_thread == t) begin
                   {r[t], q[t], d[t], count[t]} <= {32'd0, sa ? -a : a, sb ? -b : b, 6'd32};
                   remainder[t] <= f3[1];
                   negate[t] <= f3[1] ? sa : sa != sb && b != 32'd0;
                   dest[t] <= req_rd;
               end else if (count[t] != '0)
                   {r[t], q[t], count[t]} <= {r_next[t], q_next[t], count[t] - 6'd1};
       end
       wire [31:0] value = remainder[thread] ? r[thread] : q[thread];
       assign done = count[thread] == '0;
       assign result = negate[thread] ? -value : value;
       assign rd = dest[thread];
   endmodule

.. check:: test
   :verifies: core.div, core.div-time

   module tb_div;
       logic clk = 0, rst_n = 0, req = 0;
       logic [2:0] req_thread = 0, thread = 0;
       logic [1:0] f3 = 0;
       logic [31:0] a = 0, b = 0;
       logic [4:0] req_rd = 0;
       wire done;
       wire [31:0] result;
       wire [4:0] rd;
       core_div dut (.*);
       always #20 clk = !clk;

       function automatic [31:0] expect_of(input [1:0] f, input [31:0] x, y);
           case (f)
               0: return y == 0 ? 32'hffffffff : x == 32'h80000000 && y == 32'hffffffff ? x
                       : 32'($signed(x) / $signed(y));
               1: return y == 0 ? 32'hffffffff : x / y;
               2: return y == 0 ? x : x == 32'h80000000 && y == 32'hffffffff ? 0
                       : 32'($signed(x) % $signed(y));
               default: return y == 0 ? x : x % y;
           endcase
       endfunction

       int cycle = 0, fails = 0, checked = 0;
       int due [8];
       logic [31:0] want [8];
       always @(posedge clk) cycle <= cycle + 1;

       // Each cycle, each busy thread must hold done low until its due cycle, then give its result.
       task automatic watch();
           for (int t = 0; t < 8; t++) begin
               thread = 3'(t);
               #1;
               if (due[t] != 0 && done != (cycle >= due[t])) begin
                   if (fails < 10) $display("thread %0d: done=%0d at cycle %0d, due at %0d", t, done, cycle, due[t]);
                   fails++;
               end
               if (due[t] != 0 && cycle == due[t]) begin
                   if (result != want[t] || rd != 5'(t + 1)) begin
                       if (fails < 10) $display("thread %0d: result %h rd %0d, want %h", t, result, rd, want[t]);
                       fails++;
                   end
                   checked++;
                   due[t] = 0;
               end
           end
       endtask

       function automatic bit busy();
           foreach (due[t]) if (due[t] != 0) return 1;
           return 0;
       endfunction

       task automatic divide(input [1:0] f, input [31:0] x, y);
           int t = checked % 8;
           while (due[t] != 0) begin
               @(negedge clk);
               watch();
               t = (t + 1) % 8;
           end
           {req, req_thread, f3, a, b, req_rd} = {1'b1, 3'(t), f, x, y, 5'(t + 1)};
           {due[t], want[t]} = {cycle + 33, expect_of(f, x, y)};
           @(negedge clk);
           req = 0;
           watch();
       endtask

       logic [31:0] edges [10] = '{0, 1, 2, 7, 32'hffffffff, 32'h80000000, 32'h7fffffff, 32'h12345678,
                                   32'hfffffff9, 32'hdeadbeef};
       initial begin
           repeat (2) @(negedge clk);
           rst_n = 1;
           foreach (edges[i]) foreach (edges[j]) for (int f = 0; f < 4; f++) divide(2'(f), edges[i], edges[j]);
           for (int k = 0; k < 4000; k++) divide(2'(k), $urandom, k % 3 == 0 ? $urandom % 97 : $urandom);
           while (busy()) begin
               @(negedge clk);
               watch();
           end
           $display("%0d results checked, %0d failures", checked, fails);
           if (fails != 0 || checked != 4400) $fatal(1, "the divider failed");
           $finish;
       end
   endmodule

.. mutant:: build/rtl/core/core_div.v
   :kills: core.div.test

   -                negate[t] <= f3[1] ? sa : sa != sb && b != 32'd0;
   +                negate[t] <= f3[1] ? sa : sa != sb;

.. mutant:: build/rtl/core/core_div.v
   :kills: core.div.test

   -                {r[t], q[t], d[t], count[t]} <= {32'd0, sa ? -a : a, sb ? -b : b, 6'd32};
   +                {r[t], q[t], d[t], count[t]} <= {32'd0, sa ? -a : a, sb ? -b : b, 6'd33};

.. rationale::

   One step for each thread in each cycle gives a fixed time of 32 cycles, which is 5 turns. A
   radix-16 divider of ``bcw-1`` took 9 turns and 3 modules.

Registers
=========

.. requirement:: core.registers
   :parent: design.economy

   The core shall give each thread 32 registers of 32 bits, and read register 0 as zero.

.. source:: build/rtl/core/core_regfile.v
   :implements: core.registers

   module core_regfile (input wire clk,
                        input wire [bcw_params::CORE_TURN_WIDTH+4:0] ra, rb, wa,
                        input wire we, input wire [31:0] wd, output wire [31:0] a, b);
       logic [31:0] bank_a [2 ** (bcw_params::CORE_TURN_WIDTH + 5)];
       logic [31:0] bank_b [2 ** (bcw_params::CORE_TURN_WIDTH + 5)];
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
   endmodule

.. rationale::

   Two copies of the registers give two reads in one cycle from the block memory of the chip.
   Register 0 reads as zero by a compare, not by the contents of the memory.

Pipeline
========

.. definition:: core.stage
   :parent: core.core

   A :dfn:`stage` is one cycle of the work on an instruction. The core has 8 stages: fetch,
   expand, decode, read, execute, address, data and write.

.. requirement:: core.depth
   :parent: design.economy

   The core shall finish each instruction of a thread before the next turn of the thread.

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
   :implements: core.depth, core.step, core.suspend, core.div-wait, core.port-write, core.reset

   module core (input wire clk, rst_n, output wire [bcw_params::CORE_TURN_WIDTH-1:0] turn,
                output wire [31:0] fetch_addr, input wire [31:0] fetch_word,
                output wire [31:0] data_addr, output wire [3:0] data_be, output wire data_we,
                output wire [31:0] data_wdata, input wire [31:0] data_rdata,
                input wire [bcw_params::CORE_TURN_WIDTH-1:0] port_thread, input wire port_we, port_run,
                input wire [31:0] port_pc, output wire [31:0] port_rd_pc, output wire port_rd_run,
                output wire [1:0] port_rd_cause, output wire port_err,
                output wire commit, commit_resume, commit_we, output wire [1:0] commit_cause,
                output wire [bcw_params::CORE_TURN_WIDTH-1:0] commit_thread, output wire [4:0] commit_rd,
                output wire [31:0] commit_pc, commit_word, commit_a, commit_b, commit_addr, commit_load,
                output wire [31:0] commit_next, commit_value);
       localparam int T = bcw_params::CORE_THREADS, TW = bcw_params::CORE_TURN_WIDTH;
       localparam logic [1:0] NONE = 2'd0, ECALL = 2'd1, ILLEGAL = 2'd2, MISALIGNED = 2'd3;

       // The state of each thread, which only the stage W, the divider and the port write.
       logic [31:0] pc [T];
       logic run [T], waiting [T];
       logic [1:0] cause [T];
       logic [TW-1:0] rot, rot_next;
       core_rotate rotate (.turn(rot), .next(rot_next));
       assign turn = rot;

       // F: fetch the word at the program counter of the thread of the turn.
       assign fetch_addr = pc[rot];
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
       wire [31:0] a, b, w_wd;
       wire [TW+4:0] w_wa;
       wire w_we;
       core_regfile regs (.clk, .ra({d_t, d_insn[19:15]}), .rb({d_t, d_insn[24:20]}), .we(w_we), .wa(w_wa),
                          .wd(w_wd), .a, .b);
       logic r_v, r_wide, r_alt; logic [10:0] r_class; logic [1:0] r_cause; logic [TW-1:0] r_t;
       logic [31:0] r_pc, r_imm, r_word; logic [14:7] r_insn;

       // R: the registers arrive.
       logic e_v, e_wide, e_alt; logic [10:0] e_class; logic [1:0] e_cause; logic [TW-1:0] e_t;
       logic [31:0] e_pc, e_imm, e_word, e_a, e_b; logic [14:7] e_insn;

       // E: execute. The class bits are, in order, lui auipc jal jalr branch load store opimm op mul div.
       wire e_lui = e_class[10], e_auipc = e_class[9], e_jal = e_class[8], e_jalr = e_class[7];
       wire e_branch = e_class[6], e_load = e_class[5], e_store = e_class[4], e_opimm = e_class[3];
       wire e_mul = e_class[1], e_div = e_class[0];
       wire [2:0] f3 = e_insn[14:12];
       wire [31:0] alu_y, sum = e_a + e_imm, link = e_pc + (e_wide ? 32'd4 : 32'd2);
       wire taken, fault;
       core_alu alu (.f3, .alt(e_alt), .a(e_a), .b(e_opimm ? e_imm : e_b), .y(alu_y));
       core_branch compare (.f3, .a(e_a), .b(e_b), .taken);
       core_misaligned align (.size(f3[1:0]), .lo(sum[1:0]), .fault);
       wire [31:0] next = e_jal || e_branch && taken ? e_pc + e_imm : e_jalr ? {sum[31:1], 1'b0} : link;
       wire [1:0] e_stop = e_cause != NONE ? e_cause : (e_load || e_store) && fault ? MISALIGNED : NONE;
       wire [31:0] e_res = e_lui ? e_imm : e_auipc ? e_pc + e_imm : e_jal || e_jalr ? link : alu_y;
       wire e_we = e_class[10:7] != 4'd0 || e_load || e_opimm || e_class[2] || e_mul;
       wire div_done;
       wire [31:0] div_result;
       wire [4:0] div_rd;
       core_div divide (.clk, .rst_n, .req(e_v && e_div && e_stop == NONE), .req_thread(e_t), .f3(f3[1:0]),
                        .a(e_a), .b(e_b), .req_rd(e_insn[11:7]), .thread(rot_next), .done(div_done),
                        .result(div_result), .rd(div_rd));
       logic m1_v, m1_we, m1_load, m1_store, m1_mul, m1_div; logic [1:0] m1_cause; logic [TW-1:0] m1_t;
       logic [4:0] m1_rd; logic [2:0] m1_f3; logic [31:0] m1_pc, m1_word, m1_a, m1_b, m1_addr, m1_res, m1_next;

       // M1: send the address of the data, and form the partial products.
       wire [35:0] ll, lh, hl, hh;
       core_mul_part part (.f3(m1_f3[1:0]), .a(m1_a), .b(m1_b), .ll, .lh, .hl, .hh);
       core_store place (.size(m1_f3[1:0]), .lo(m1_addr[1:0]), .data(m1_b), .be(data_be), .wdata(data_wdata));
       assign data_addr = m1_addr;
       assign data_we = m1_v && m1_store && m1_cause == NONE;
       logic m2_v, m2_we, m2_load, m2_mul, m2_div; logic [1:0] m2_cause; logic [TW-1:0] m2_t;
       logic [4:0] m2_rd; logic [2:0] m2_f3; logic [31:0] m2_pc, m2_word, m2_a, m2_b, m2_addr, m2_res, m2_next;
       logic [35:0] m2_ll, m2_lh, m2_hl, m2_hh;

       // M2: the loaded word arrives, and the partial products add up.
       wire [31:0] product;
       core_mul_sum total (.f3(m2_f3[1:0]), .ll(m2_ll), .lh(m2_lh), .hl(m2_hl), .hh(m2_hh), .y(product));
       logic w_v, w_we_r, w_load, w_div; logic [1:0] w_cause; logic [TW-1:0] w_t; logic [4:0] w_rd;
       logic [2:0] w_f3; logic [31:0] w_pc, w_word, w_a, w_b, w_addr, w_res, w_next, w_data;

       // W: the one place that an instruction changes the state of its thread.
       wire [31:0] loaded;
       core_load extract (.f3(w_f3), .lo(w_addr[1:0]), .word(w_data), .y(loaded));
       wire retire = w_v && w_cause == NONE;
       wire resume = waiting[rot_next] && div_done;
       assign w_we = retire && w_we_r || resume;
       assign w_wa = resume ? {rot_next, div_rd} : {w_t, w_rd};
       assign w_wd = resume ? div_result : w_load ? loaded : w_res;

       // Each change of the state of a thread, for the proofs and the tests.
       assign {commit, commit_resume, commit_we, commit_cause, commit_thread, commit_rd}
           = {w_v || resume, resume, w_we, resume ? NONE : w_cause, resume ? rot_next : w_t, w_wa[4:0]};
       assign {commit_pc, commit_word, commit_a, commit_b, commit_addr, commit_load, commit_next, commit_value}
           = {w_pc, w_word, w_a, w_b, w_addr, w_data, w_next, w_wd};

       // The port writes a thread only while it is suspended, with no divide and no port write pending.
       logic q_we, q_run; logic [TW-1:0] q_thread; logic [31:0] q_pc;
       assign port_err = port_we && (run[port_thread] || waiting[port_thread] || q_we && q_thread == port_thread);
       assign {port_rd_pc, port_rd_run, port_rd_cause} = {pc[port_thread], run[port_thread], cause[port_thread]};

       always_ff @(posedge clk) begin
           rot <= rst_n ? rot_next : '0;
           {q_we, q_thread, q_pc, q_run} <= {rst_n && port_we && !port_err, port_thread, port_pc, port_run};
           {x_v, x_t, x_pc} <= {rst_n && run[rot] && !waiting[rot], rot, pc[rot]};
           {d_v, d_t, d_pc, d_insn, d_word, d_bad, d_wide} <= {rst_n && x_v, x_t, x_pc, x_insn, fetch_word, x_bad, x_wide};
           {r_v, r_t, r_pc, r_word, r_insn, r_imm, r_wide, r_alt} <= {rst_n && d_v, d_t, d_pc, d_word, d_insn[14:7],
                                                                      d_imm, d_wide, alt};
           r_class <= {lui, auipc, jal, jalr, branch, load, store, opimm, op, mul, div};
           r_cause <= ecall ? ECALL : d_bad || illegal ? ILLEGAL : NONE;
           {e_v, e_t, e_pc, e_word, e_insn, e_imm, e_wide, e_alt, e_class, e_cause, e_a, e_b}
               <= {rst_n && r_v, r_t, r_pc, r_word, r_insn, r_imm, r_wide, r_alt, r_class, r_cause, a, b};
           {m1_v, m1_t, m1_pc, m1_word, m1_a, m1_b, m1_cause, m1_rd, m1_f3, m1_addr, m1_res, m1_next}
               <= {rst_n && e_v, e_t, e_pc, e_word, e_a, e_b, e_stop, e_insn[11:7], f3, sum, e_res, next};
           {m1_we, m1_load, m1_store, m1_mul, m1_div} <= {e_we, e_load, e_store, e_mul, e_div};
           {m2_v, m2_t, m2_pc, m2_word, m2_a, m2_b, m2_cause, m2_rd, m2_f3, m2_addr, m2_res, m2_next}
               <= {rst_n && m1_v, m1_t, m1_pc, m1_word, m1_a, m1_b, m1_cause, m1_rd, m1_f3, m1_addr, m1_res, m1_next};
           {m2_we, m2_load, m2_mul, m2_div, m2_ll, m2_lh, m2_hl, m2_hh} <= {m1_we, m1_load, m1_mul, m1_div, ll, lh, hl, hh};
           {w_v, w_t, w_pc, w_word, w_a, w_b, w_cause, w_rd, w_f3, w_addr, w_next, w_data}
               <= {rst_n && m2_v, m2_t, m2_pc, m2_word, m2_a, m2_b, m2_cause, m2_rd, m2_f3, m2_addr, m2_next, data_rdata};
           {w_we_r, w_load, w_div, w_res} <= {m2_we, m2_load, m2_div, m2_mul ? product : m2_res};
       end

       always_ff @(posedge clk)
           if (!rst_n)
               for (int t = 0; t < T; t++) {pc[t], run[t], waiting[t], cause[t]} <= {32'd0, t == 0, 1'b0, NONE};
           else begin
               if (retire) {pc[w_t], waiting[w_t]} <= {w_next, w_div};
               else if (w_v) {run[w_t], cause[w_t]} <= {1'b0, w_cause};
               if (resume) waiting[rot_next] <= 1'b0;
               if (q_we) {pc[q_thread], run[q_thread]} <= {q_pc, q_run};
           end
   endmodule

.. check:: prove
   :verifies: core.depth, core.step, core.suspend

   module core_props (input wire clk, input wire [31:0] fetch_word, data_rdata, port_pc,
                      input wire [2:0] port_thread, input wire port_we, port_run);
       logic rst_n = 1'b0;
       always_ff @(posedge clk) rst_n <= 1'b1;
       wire [2:0] turn, commit_thread;
       wire [31:0] fetch_addr, data_addr, data_wdata, port_rd_pc;
       wire [3:0] data_be;
       wire data_we, port_rd_run, port_err, commit, commit_resume, commit_we;
       wire [1:0] port_rd_cause, commit_cause;
       wire [4:0] commit_rd;
       wire [31:0] commit_pc, commit_word, commit_a, commit_b, commit_addr, commit_load, commit_next, commit_value;
       core dut (.*);

       // core.depth: an instruction commits 7 cycles after the turn of its thread, so before its next turn.
       logic [20:0] turns;
       always_ff @(posedge clk) turns <= {turns[17:0], turn};
       wire step = rst_n && commit && !commit_resume;
       always_comb if (step) assert (commit_thread == turns[20:18]);

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
       wire [1:0] cause = ecall ? 2'd1 : bad || illegal ? 2'd2 : (load || store) && fault ? 2'd3 : 2'd0;
       wire [31:0] next = jal || branch && taken ? commit_pc + imm : jalr ? {addr[31:1], 1'b0} : link;
       wire we = lui || auipc || jal || jalr || load || opimm || op || mul;
       wire [31:0] value = lui ? imm : auipc ? commit_pc + imm : jal || jalr ? link : load ? loaded
                         : mul ? product : alu_y;
       wire done = step && cause == 2'd0;
       always_comb if (step) assert (commit_cause == cause);
       always_comb if (done) assert (commit_next == next && commit_we == we);
       always_comb if (done && we) assert (commit_rd == insn[11:7]);
       // The solver cannot relate the multiply after the registers of the pipeline to a multiply
       // here. The equiv of core.mul proves the units, and the test runs them in the pipeline.
       always_comb if (done && we && !mul) assert (commit_value == value);
       always_comb if (done && (load || store)) assert (commit_addr == addr);
   endmodule

.. mutant:: build/rtl/core/core.v
   :kills: core.depth.prove

   -    wire [31:0] next = e_jal || e_branch && taken ? e_pc + e_imm : e_jalr ? {sum[31:1], 1'b0} : link;
   +    wire [31:0] next = e_jal || e_branch ? e_pc + e_imm : e_jalr ? {sum[31:1], 1'b0} : link;

.. rationale::

   With as many stages as threads, an instruction finishes before the next instruction of its
   thread starts. The core needs no forwarding and no stall, and it writes the state of a
   thread in one place.

Suspension
==========

.. definition:: core.suspended
   :parent: core.thread

   The core fetches nothing in the turns of a :dfn:`suspended` thread.

.. requirement:: core.suspend
   :parent: design.economy

   If an instruction is illegal or ``ECALL`` or has its access refused, then the core shall
   suspend its thread with its program counter on the instruction.

.. requirement:: core.div-wait
   :parent: core.div

   While the divide of a thread runs, the core shall fetch nothing in the turns of the thread.

.. rationale::

   The supervisor handles each suspension. It moves the program counter past an ``ECALL`` that
   it accepts, and it can do an access that the core refused.

Thread control
==============

.. definition:: core.port
   :parent: core.core

   The :dfn:`port` of the core reads the program counter, the cause and the run state of a
   thread, and writes the program counter and the run state.

.. requirement:: core.port-write
   :parent: design.auditability

   When the port writes a thread, the core shall accept the write only for a suspended thread
   with no divide and no other write of the port pending.

.. requirement:: core.reset
   :parent: design.economy

   When the core leaves reset, the core shall run thread 0 from address 0, and hold each other
   thread suspended.

.. check:: test
   :verifies: core.registers, core.step, core.suspend, core.div-wait, core.port-write, core.reset

   module tb_core;
       logic clk = 0, rst_n = 0;
       logic [31:0] fetch_addr, fetch_word, data_addr, data_wdata, data_rdata;
       logic [3:0] data_be;
       logic data_we;
       logic [2:0] port_thread = 0;
       logic port_we = 0, port_run = 0;
       logic [31:0] port_pc = 0, port_rd_pc;
       logic port_rd_run, port_err;
       logic [1:0] port_rd_cause;
       wire [2:0] turn, commit_thread;
       wire commit, commit_resume, commit_we;
       wire [1:0] commit_cause;
       wire [4:0] commit_rd;
       wire [31:0] commit_pc, commit_word, commit_a, commit_b, commit_addr, commit_load, commit_next, commit_value;
       core dut (.*);

       logic [7:0] mem [65536];
       always @(posedge clk) begin
           fetch_word <= {mem[16'(fetch_addr + 3)], mem[16'(fetch_addr + 2)], mem[16'(fetch_addr + 1)],
                          mem[16'(fetch_addr)]};
           data_rdata <= {mem[16'({data_addr[31:2], 2'd3})], mem[16'({data_addr[31:2], 2'd2})],
                          mem[16'({data_addr[31:2], 2'd1})], mem[16'({data_addr[31:2], 2'd0})]};
           if (data_we)
               for (int i = 0; i < 4; i++)
                   if (data_be[i]) mem[16'({data_addr[31:2], 2'(i)})] <= data_wdata[8 * i +: 8];
       end
       always #5 clk = !clk;

       function [31:0] enc_i(input [11:0] imm_f, input [4:0] rs1_f, input [2:0] fn3, input [4:0] rd_f,
                             input [6:0] op_f);
           enc_i = {imm_f, rs1_f, fn3, rd_f, op_f};
       endfunction
       function [31:0] enc_s(input [11:0] imm_f, input [4:0] rs2_f, input [4:0] rs1_f, input [2:0] fn3,
                             input [6:0] op_f);
           enc_s = {imm_f[11:5], rs2_f, rs1_f, fn3, imm_f[4:0], op_f};
       endfunction
       function [31:0] enc_r(input [6:0] f7_f, input [4:0] rs2_f, input [4:0] rs1_f, input [2:0] fn3,
                             input [4:0] rd_f, input [6:0] op_f);
           enc_r = {f7_f, rs2_f, rs1_f, fn3, rd_f, op_f};
       endfunction
       function [31:0] enc_b(input [12:1] imm_f, input [4:0] rs2_f, input [4:0] rs1_f, input [2:0] fn3,
                             input [6:0] op_f);
           enc_b = {imm_f[12], imm_f[10:5], rs2_f, rs1_f, fn3, imm_f[4:1], imm_f[11], op_f};
       endfunction
       function [31:0] enc_j(input [20:1] imm_f, input [4:0] rd_f, input [6:0] op_f);
           enc_j = {imm_f[20], imm_f[10:1], imm_f[11], imm_f[19:12], rd_f, op_f};
       endfunction

       int at;
       task automatic put(input [31:0] word);
           {mem[16'(at + 3)], mem[16'(at + 2)], mem[16'(at + 1)], mem[16'(at)]} = word;
           at += 4;
       endtask
       task automatic put16(input [15:0] half);
           {mem[16'(at + 1)], mem[16'(at)]} = half;
           at += 2;
       endtask
       task automatic li(input [4:0] rd, input [31:0] value);
           logic [31:0] upper = (value + 32'h800) >> 12;
           put({upper[19:0], rd, 7'd55});
           put(enc_i(12'(value - (upper << 12)), rd, 3'd0, rd, 7'd19));
       endtask
       // Stores register rs at the next word of the results of the thread, and records what it should be.
       int out;
       logic [31:0] want [int];
       task automatic keep(input [4:0] rs, input [31:0] value);
           li(5'd31, 32'(out));
           put(enc_s(12'd0, rs, 5'd31, 3'd2, 7'd35));
           want[out] = value;
           out += 4;
       endtask
       function automatic [31:0] word_at(input int a);
           return {mem[16'(a + 3)], mem[16'(a + 2)], mem[16'(a + 1)], mem[16'(a)]};
       endfunction

       localparam logic [31:0] ECALL = 32'h73;
       logic [31:0] ops [$] = '{0, 1, 2, 7, 32'hffffffff, 32'h80000000, 32'h7fffffff, 32'h12345678, 32'hfffffff9,
                                 32'hdeadbeef};
       int fails = 0;

       // Thread 0: every class of instruction but the divide, then ECALL.
       task automatic program0();
           int here;
           at = 0; out = 32'h8000;
           li(5'd1, 32'h12345678); li(5'd2, 32'hfffffff9);
           put(enc_r(7'd0, 5'd2, 5'd1, 3'd0, 5'd3, 7'd51));  keep(5'd3, 32'h12345678 + 32'hfffffff9);
           put(enc_r(7'd32, 5'd2, 5'd1, 3'd0, 5'd3, 7'd51)); keep(5'd3, 32'h12345678 - 32'hfffffff9);
           put(enc_r(7'd0, 5'd2, 5'd1, 3'd1, 5'd3, 7'd51));  keep(5'd3, 32'h12345678 << 25);
           put(enc_r(7'd0, 5'd2, 5'd1, 3'd2, 5'd3, 7'd51));  keep(5'd3, 0);
           put(enc_r(7'd0, 5'd2, 5'd1, 3'd3, 5'd3, 7'd51));  keep(5'd3, 1);
           put(enc_r(7'd32, 5'd1, 5'd2, 3'd5, 5'd3, 7'd51)); keep(5'd3, 32'hffffffff);
           put(enc_i(12'd4, 5'd2, 3'd5, 5'd3, 7'd19));       keep(5'd3, 32'h0fffffff);
           put(enc_i({7'd32, 5'd4}, 5'd2, 3'd5, 5'd3, 7'd19)); keep(5'd3, 32'hffffffff);
           put(enc_i(12'hff0, 5'd1, 3'd7, 5'd3, 7'd19));     keep(5'd3, 32'h12345670);
           put(enc_r(7'd1, 5'd2, 5'd1, 3'd0, 5'd3, 7'd51));  keep(5'd3, 32'h12345678 * 32'hfffffff9);
           put(enc_r(7'd1, 5'd2, 5'd1, 3'd1, 5'd3, 7'd51));  keep(5'd3, 32'hffffffff);
           put(enc_r(7'd1, 5'd2, 5'd1, 3'd3, 5'd3, 7'd51));  keep(5'd3, 32'h12345677);
           // Store a byte and a half, and load them back signed and unsigned.
           li(5'd4, 32'h9000);
           put(enc_s(12'd1, 5'd2, 5'd4, 3'd0, 7'd35));
           put(enc_s(12'd2, 5'd2, 5'd4, 3'd1, 7'd35));
           put(enc_i(12'd1, 5'd4, 3'd0, 5'd3, 7'd3));        keep(5'd3, 32'hfffffff9);
           put(enc_i(12'd1, 5'd4, 3'd4, 5'd3, 7'd3));        keep(5'd3, 32'h000000f9);
           put(enc_i(12'd2, 5'd4, 3'd1, 5'd3, 7'd3));        keep(5'd3, 32'hfffffff9);
           put(enc_i(12'd2, 5'd4, 3'd5, 5'd3, 7'd3));        keep(5'd3, 32'h0000fff9);
           // A taken branch skips an addi; a not-taken one does not.
           li(5'd3, 0);
           put(enc_b(12'd4, 5'd2, 5'd1, 3'd1, 7'd99));
           put(enc_i(12'd1, 5'd3, 3'd0, 5'd3, 7'd19));
           put(enc_b(12'd4, 5'd2, 5'd1, 3'd0, 7'd99));
           put(enc_i(12'd2, 5'd3, 3'd0, 5'd3, 7'd19));       keep(5'd3, 2);
           // jal links and jumps; auipc; compressed c.li x5, 7 and c.addi x5, 1.
           here = at;
           put(enc_j(20'd4, 5'd6, 7'd111));
           put(enc_i(12'd1, 5'd3, 3'd0, 5'd3, 7'd19));
           put(enc_i(12'd0, 5'd6, 3'd0, 5'd7, 7'd19));       keep(5'd7, 32'(here + 4));
           here = at;
           put({20'd1, 5'd8, 7'd23});                        keep(5'd8, 32'(here + 32'h1000));
           put16(16'h429d); put16(16'h0285);                 keep(5'd5, 8);
           put(enc_i(12'd5, 5'd1, 3'd0, 5'd0, 7'd19));
           put(enc_i(12'd0, 5'd0, 3'd0, 5'd3, 7'd19));       keep(5'd3, 0);
           put(ECALL);
       endtask

       // Thread 1: each divide and remainder of every pair of ops, then ECALL.
       task automatic program1();
           at = 32'h2000; out = 32'ha000;
           foreach (ops[i]) foreach (ops[j]) begin
               li(5'd1, ops[i]); li(5'd2, ops[j]);
               for (int f = 4; f < 8; f++) begin
                   put(enc_r(7'd1, 5'd2, 5'd1, 3'(f), 5'd3, 7'd51));
                   keep(5'd3, expect_div(f, ops[i], ops[j]));
               end
           end
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

       task automatic start(input [2:0] t, input [31:0] pc);
           @(negedge clk);
           {port_thread, port_pc, port_run, port_we} = {t, pc, 1'b1, 1'b1};
           #1;
           if (port_err) begin $display("FAIL: the port refused to start thread %0d", t); fails++; end
           @(negedge clk);
           port_we = 0;
       endtask

       task automatic expect_stop(input [2:0] t, input [1:0] cause, input [31:0] pc);
           port_thread = t;
           #1;
           if (port_rd_run || port_rd_cause != cause || port_rd_pc != pc) begin
               $display("FAIL: thread %0d run=%0d cause=%0d pc=%h, want cause %0d at pc %h", t, port_rd_run,
                        port_rd_cause, port_rd_pc, cause, pc);
               fails++;
           end
       endtask

       int ecall0, ecall1;
       initial begin
           foreach (mem[i]) mem[i] = 0;
           program0(); ecall0 = at - 4;
           program1(); ecall1 = at - 4;
           // Thread 2 meets an illegal instruction; thread 3 a misaligned load.
           at = 32'h6000; put(32'hffffffff);
           at = 32'h6100; put(enc_i(12'd2, 5'd0, 3'd2, 5'd3, 7'd3));
           repeat (4) @(negedge clk);
           rst_n = 1;
           start(3'd1, 32'h2000); start(3'd2, 32'h6000); start(3'd3, 32'h6100);
           // A second write to a thread while the first is pending is refused.
           @(negedge clk); {port_thread, port_pc, port_run, port_we} = {3'd4, 32'h6100, 1'b0, 1'b1};
           @(negedge clk); {port_thread, port_pc, port_run, port_we} = {3'd4, 32'h6000, 1'b1, 1'b1};
           #1 if (!port_err) begin $display("FAIL: the port wrote a thread with a write pending"); fails++; end
           @(negedge clk); port_we = 0;
           // A write to a running thread is refused.
           @(negedge clk); {port_thread, port_pc, port_run, port_we} = {3'd1, 32'd0, 1'b0, 1'b1};
           #1 if (!port_err) begin $display("FAIL: the port wrote a running thread"); fails++; end
           @(negedge clk); port_we = 0;
           repeat (400000) @(negedge clk);
           expect_stop(3'd0, 2'd1, 32'(ecall0));
           expect_stop(3'd1, 2'd1, 32'(ecall1));
           expect_stop(3'd2, 2'd2, 32'h6000);
           expect_stop(3'd3, 2'd3, 32'h6100);
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

   -    assign port_err = port_we && (run[port_thread] || waiting[port_thread] || q_we && q_thread == port_thread);
   +    assign port_err = port_we && (run[port_thread] || waiting[port_thread]);

.. mutant:: build/rtl/core/core.v
   :kills: core.registers.test

   -            for (int t = 0; t < T; t++) {pc[t], run[t], waiting[t], cause[t]} <= {32'd0, t == 0, 1'b0, NONE};
   +            for (int t = 0; t < T; t++) {pc[t], run[t], waiting[t], cause[t]} <= {32'd0, 1'b1, 1'b0, NONE};
