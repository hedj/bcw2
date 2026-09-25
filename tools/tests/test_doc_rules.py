"""Tests of the documentation rules that need the whole book, one class per rule.

Each test changes one thing in GOOD from test_check.py, and expects exactly the
findings of the rule that the change breaks.
"""

import sys
import tempfile
import unittest
from pathlib import Path

from test_check import GOOD, ROOT, findings, line, run_book

sys.path.insert(0, str(ROOT / "tools"))

import check  # noqa: E402

REQUIREMENT = "**REQUIREMENT.**"


class ImplementedTest(unittest.TestCase):
    """doc.implemented"""

    def without_verilog(self):
        return GOOD.replace(" implements=core.rotation}", "}")

    def test_a_requirement_that_nothing_implements_is_a_finding(self):
        text = self.without_verilog()
        self.assertEqual(findings(text), [(line(text, REQUIREMENT), "implemented", "core.rotation")])

    def test_impl_none_is_an_exit(self):
        text = self.without_verilog().replace("parent=design.timing}", "parent=design.timing impl=none}", 1)
        self.assertEqual(findings(text), [])

    def test_a_tool_comment_implements_it(self):
        self.assertEqual(findings(self.without_verilog(), implemented={"core.rotation"}), [])

    def test_an_implements_list_can_name_several_anchors(self):
        text = GOOD.replace("implements=core.rotation}", "implements=core.core,core.rotation}")
        self.assertEqual(findings(text), [])

    def test_only_a_verilog_block_implements(self):
        text = GOOD.replace("{.verilog file=", "{.python file=")
        self.assertEqual(findings(text), [(line(text, REQUIREMENT), "implemented", "core.rotation")])

    def test_tool_implements_reads_whole_comment_lines_only(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "tool.py"
            path.write_text("# implements: doc.a\n    # implements: doc.b\nx = '# implements: doc.c'\n")
            self.assertEqual(check.tool_implements([path]), {"doc.a", "doc.b"})

    def test_the_command_reads_the_comments_in_tools(self):
        result = run_book(self.without_verilog(), tool="# implements: core.rotation\n")
        self.assertEqual(result.returncode, 0, result.stdout)
        result = run_book(self.without_verilog(), tool="")
        self.assertEqual(result.returncode, 1, result.stdout)


if __name__ == "__main__":
    unittest.main()
