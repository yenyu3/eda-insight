import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from eda_tools.flowchart_extractor import extract_flowchart

SAMPLES = ROOT / "sample_verilog"


def load_sample(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8")


class FlowchartExtractorTests(unittest.TestCase):
    def test_counter_if_else_shape(self):
        data = extract_flowchart(load_sample("counter_4bit.v"))
        block = data["always_blocks"][0]
        labels = {node["label"] for node in block["nodes"]}
        self.assertIn("reset", labels)
        self.assertIn("enable", labels)
        self.assertTrue(any("count <= 4'b0000" in label for label in labels))
        self.assertTrue(any("count <= count + 1" in label for label in labels))

    def test_adder_assign_only(self):
        data = extract_flowchart(load_sample("adder_8bit.v"))
        self.assertEqual(data["always_blocks"], [])
        self.assertEqual(data["assign_blocks"][0]["output"], "{cout, sum}")

    def test_alu_case_branches_and_truncation(self):
        data = extract_flowchart(load_sample("alu_8bit.v"))
        branch_labels = {edge.get("label") for edge in data["always_blocks"][0]["edges"]}
        self.assertTrue({"OP_ADD", "OP_SUB", "OP_AND", "OP_OR"}.issubset(branch_labels))
        self.assertTrue(data["truncated"])
        self.assertIn("case_arm_limit", data["truncation_reasons"])

    def test_traffic_light_state_case(self):
        data = extract_flowchart(load_sample("traffic_light.v"))
        branch_labels = {edge.get("label") for edge in data["always_blocks"][0]["edges"]}
        self.assertTrue({"S_RED", "S_GREEN", "S_YELLOW", "default"}.issubset(branch_labels))
        self.assertEqual(data["always_blocks"][0]["block_role"], "fsm")

    def test_uart_sequence_then_case_and_nested_decisions(self):
        data = extract_flowchart(load_sample("uart_tx.v"))
        labels = {node["label"] for node in data["always_blocks"][0]["nodes"]}
        self.assertIn("case(state)", labels)
        self.assertIn("tx_valid", labels)
        self.assertIn("baud_tick", labels)
        self.assertIn("bit_cnt == 3'd7", labels)
        self.assertTrue(any(label.startswith("baud_cnt <=") for label in labels))

    def test_inline_if_else_fixture(self):
        code = """
module inline_if(input clk, input sel, input a, input b, output reg y);
always @(posedge clk) begin
  if (sel) y <= a; else y <= b;
end
endmodule
"""
        data = extract_flowchart(code)
        block = data["always_blocks"][0]
        labels = {node["label"] for node in block["nodes"]}
        edge_labels = {edge.get("label") for edge in block["edges"]}
        self.assertIn("sel", labels)
        self.assertTrue(any("y <= a" in label for label in labels))
        self.assertTrue(any("y <= b" in label for label in labels))
        self.assertTrue({"YES", "NO"}.issubset(edge_labels))

    def test_systemverilog_always_comb(self):
        code = """
module sv_comb(input logic a, output logic y);
always_comb begin
  y = a;
end
endmodule
"""
        data = extract_flowchart(code)
        self.assertEqual(data["always_blocks"][0]["trigger"], "always_comb")
        self.assertEqual(data["always_blocks"][0]["trigger_type"], "combinational")


if __name__ == "__main__":
    unittest.main()
