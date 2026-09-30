"""Tests of tools/timing.py: real yosys and nextpnr on a small design, and the verdict of main."""

import json

import pytest

import timing

COUNTER = "module counter (input wire clk, output reg [7:0] count);\n    always @(posedge clk) count <= count + 8'd1;\nendmodule\n"


def test_a_small_design_is_placed_and_routed_to_its_maximum_frequency(tmp_path):
    source = tmp_path / "counter.v"
    source.write_text(COUNTER)
    assert timing.synthesise([str(source)], "counter", tmp_path / "top.json") is None
    fmax = timing.place(tmp_path / "top.json", 50, 1, tmp_path / "seed-1.log")
    assert fmax > 50
    assert "Max frequency for clock" in (tmp_path / "seed-1.log").read_text()


def test_a_design_that_does_not_build_gives_the_output_of_yosys(tmp_path):
    source = tmp_path / "broken.v"
    source.write_text("module broken (input wire clk);\n    assign = ;\nendmodule\n")
    assert "ERROR" in timing.synthesise([str(source)], "broken", tmp_path / "top.json")


@pytest.mark.parametrize("frequencies, status", [
    ({1: 90.0, 2: 86.0, 3: 99.0}, 0),
    ({1: 80.0, 2: 86.0, 3: 70.0}, 0),
    ({1: None, 2: None, 3: 99.0}, 0),
    ({1: 80.0, 2: None, 3: 84.9}, 1),
    ({1: None, 2: None, 3: None}, 1),
], ids=["each seed reaches the clock", "one seed reaches the clock", "two runs fail and one reaches the clock",
        "no seed reaches the clock", "every run fails"])
def test_the_exit_is_0_if_a_seed_reaches_the_clock(frequencies, status, tmp_path, monkeypatch, capsys):
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "checks.json").write_text(json.dumps({"constants": {"CORE_CLOCK": 85 * 10 ** 6}}))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(timing, "sources", lambda: [])
    monkeypatch.setattr(timing, "synthesise", lambda files, top, netlist: None)
    monkeypatch.setattr(timing, "place", lambda netlist, mhz, seed, log: frequencies[seed])
    monkeypatch.delenv("SEEDS", raising=False)
    assert timing.main() == status
    output = capsys.readouterr().out
    assert "timing: seed 3:" in output and "timing: seed 4:" not in output
    assert ("minimum" in output) == any(value is not None for value in frequencies.values())


def test_seeds_in_the_environment_sets_the_number_of_seeds(monkeypatch):
    monkeypatch.setenv("SEEDS", "32")
    assert timing.seed_count() == 32


@pytest.mark.parametrize("text", ["0", "-2", "three", ""])
def test_seeds_that_is_not_a_whole_number_from_1_stops_with_a_message(text, monkeypatch):
    monkeypatch.setenv("SEEDS", text)
    with pytest.raises(SystemExit, match="SEEDS must be a whole number from 1"):
        timing.seed_count()


def test_a_tangle_without_the_clock_stops_with_a_message(tmp_path, monkeypatch):
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "checks.json").write_text(json.dumps({"constants": {}}))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="no CORE_CLOCK"):
        timing.clock_mhz()
