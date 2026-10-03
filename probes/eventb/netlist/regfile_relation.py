"""regfile_relation.py GOLD_PORTS GATE_PORTS OUT.v: the one-step check of the core's register file. Gold's memory
is a function of the gate's state: word i is the delayed write data when the delayed write enable is
set and the delayed write address is i, else word i of the block RAM (bits 31:0). From any gate
state and inputs, one step must keep that relation, and the outputs of the next states must agree
(gold's read registers affect only its outputs, and gold may power up in any state)."""
import json
import sys

gold = json.load(open(sys.argv[1])); gate = json.load(open(sys.argv[2])); out = sys.argv[3]
gw, tw, fed = gold["widths"], gate["widths"], gate["fed"]
esc = lambda name: "\\" + name + " "
inputs = {"ra": 9, "rb": 9, "wa": 9, "we": 1, "wd": 32}
lines = ["module rf_check(input clk, " + ", ".join(f"input [{w - 1}:0] {n}, {n}2" for n, w in inputs.items()) + ",",
         f"    input [{sum(tw.values()) - 1}:0] gs, input [63:0] gold_read, input [1:0] gold_zero, output bad);", "    wire ok;"]
offset, gate_q, gate_at = 0, {}, {}
for name, w in tw.items():
    gate_q[name] = f"gs[{offset + w - 1}:{offset}]"; gate_at[name] = offset; offset += w
for c in ("c1", "c2"):
    lines += [f"    wire [{w - 1}:0] {c}_{i};" for i, (n, w) in enumerate(tw.items())]
idx = {n: i for i, n in enumerate(tw)}


def pending(prefix, src):   # the delayed write, from a gate state given as src(name) -> expression
    sel = {}
    for key, port in fed.items():
        net, bit = key.rsplit("/", 1)
        here = src(net)    # a part-select of a part-select is not Verilog: index gs directly
        sel.setdefault(port.split("[")[0], {})[int(port.split("[")[1][:-1])] = f"gs[{gate_at[net] + int(bit)}]" if here is None else f"{here}[{bit}]"
    lines.append(f"    wire {prefix}_we = {sel['we'][0]};")
    lines.append(f"    wire [8:0] {prefix}_wa = {{{', '.join(sel['wa'][k] for k in range(8, -1, -1))}}};")
    lines.append(f"    wire [31:0] {prefix}_wd = {{{', '.join(sel['wd'][k] for k in range(31, -1, -1))}}};")


pending("now", lambda n: None)
pending("next", lambda n: f"c1_{idx[n]}")
conn = lambda port_map: ", ".join(f".{esc(p)}({e})" for p, e in port_map.items())
c1 = {f"q:{n}": gate_q[n] for n in tw} | {f"d:{n}": f"c1_{idx[n]}" for n in tw} | {n: n for n in inputs} | {"clk": "clk", "a": "", "b": ""}
c2 = {f"q:{n}": f"c1_{idx[n]}" for n in tw} | {f"d:{n}": "" for n in tw} | {n: f"{n}2" for n in inputs} | {"clk": "clk", "a": "gate_a", "b": "gate_b"}
lines += ["    wire [31:0] gate_a, gate_b, gold_a, gold_b;",
          f"    gate_ev c1 ({conn(c1)});", f"    gate_ev c2 ({conn(c2)});"]
g1, g2, checks = {n: n for n in inputs} | {"clk": "clk", "a": "", "b": ""}, {n: f"{n}2" for n in inputs} | {"clk": "clk", "a": "gold_a", "b": "gold_b"}, []
for bank in ("a", "b"):
    ram = f"bank_{bank}.0.0.mem"
    for i in range(512):
        word = f"bank_{bank}[{i}]"
        if word not in gw or f"{ram}[{i}]" not in tw:
            raise SystemExit(f"no state port for {word} or {ram}[{i}]")
        lines.append(f"    wire [31:0] g_{bank}{i}_now = now_we && now_wa == 9'd{i} ? now_wd : gs[{gate_at[f'{ram}[{i}]'] + 31}:{gate_at[f'{ram}[{i}]']}];")
        lines.append(f"    wire [31:0] g_{bank}{i}_want = next_we && next_wa == 9'd{i} ? next_wd : c1_{idx[f'{ram}[{i}]']}[31:0];")
        lines.append(f"    wire [31:0] g_{bank}{i}_next;")
        g1[f"q:{word}"] = f"g_{bank}{i}_now"; g1[f"d:{word}"] = f"g_{bank}{i}_next"
        g2[f"q:{word}"] = "32'd0"; g2[f"d:{word}"] = ""
        checks.append(f"g_{bank}{i}_next == g_{bank}{i}_want")
for k, bank in enumerate("ab"):
    lines.append(f"    wire [31:0] read_{bank}_next; wire zero_{bank}_next;")
    g1[f"q:read_{bank}"] = f"gold_read[{32 * k + 31}:{32 * k}]"; g1[f"d:read_{bank}"] = f"read_{bank}_next"
    g1[f"q:zero_{bank}"] = f"gold_zero[{k}]"; g1[f"d:zero_{bank}"] = f"zero_{bank}_next"
    g2[f"q:read_{bank}"] = f"read_{bank}_next"; g2[f"d:read_{bank}"] = ""
    g2[f"q:zero_{bank}"] = f"zero_{bank}_next"; g2[f"d:zero_{bank}"] = ""
missing = set(f"{d}:{n}" for n in gw for d in "qd") - set(g1)
if missing:
    raise SystemExit(f"gold state ports not connected: {sorted(missing)[:5]}")
lines += [f"    gold_ev g1 ({conn(g1)});", f"    gold_ev g2 ({conn(g2)});",
          "    assign bad = !ok;",
          "    assign ok = gate_a == gold_a && gate_b == gold_b && " + " && ".join(checks) + ";", "endmodule"]
open(out, "w").write("\n".join(lines) + "\n")
