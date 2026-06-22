"""
models/analysis_result.py — EDA 分析結果資料模型

整合 parser / lint / simulation / synthesis / AI 各階段的輸出，
提供統一格式供 API routes 組裝回應。
"""

from __future__ import annotations
from typing import Optional


class AnalysisResult:
    """一次 run 的完整分析結果，對應 GET /api/result/<run_id> 的回應格式。"""

    def __init__(
        self,
        run_id: str,
        filename: str,
        parser_result: Optional[dict] = None,
        workflow_plan: Optional[dict] = None,
        waveform: Optional[dict] = None,
        synthesis: Optional[dict] = None,
        dependency_graph: Optional[dict] = None,
        ai_summary: Optional[str] = None,
        risk_scores: Optional[dict] = None,
        bottleneck_analysis: Optional[dict] = None,
        flowchart: Optional[dict] = None,
    ):
        self.run_id = run_id
        self.filename = filename
        self.parser_result = parser_result
        self.workflow_plan = workflow_plan
        self.waveform = waveform
        self.synthesis = synthesis
        self.dependency_graph = dependency_graph
        self.ai_summary = ai_summary
        self.risk_scores = risk_scores
        self.bottleneck_analysis = bottleneck_analysis
        self.flowchart = flowchart

    @property
    def lint_issues(self) -> list:
        """從 parser_result 直接取出 lint_issues 列表。"""
        return (self.parser_result or {}).get("lint_issues", [])

    @property
    def modules(self) -> list:
        """從 parser_result 直接取出 modules 列表。"""
        return (self.parser_result or {}).get("modules", [])

    def to_dict(self) -> dict:
        """序列化為 API /api/result 回應格式。"""
        return {
            "run_id": self.run_id,
            "filename": self.filename,
            "parser_result": self.parser_result,
            "workflow_plan": self.workflow_plan,
            "waveform": self.waveform,
            "synthesis": self.synthesis,
            "dependency_graph": self.dependency_graph,
            "ai_summary": self.ai_summary,
            "risk_scores": self.risk_scores,
            "bottleneck_analysis": self.bottleneck_analysis,
            "lint_issues": self.lint_issues,
            "flowchart": self.flowchart,
        }

    def __repr__(self) -> str:
        return f"<AnalysisResult run={self.run_id[:8]} modules={len(self.modules)} lint={len(self.lint_issues)}>"


class SynthesisMetrics:
    """合成階段的 PPA 指標，對應 Yosys 輸出。"""

    def __init__(
        self,
        cell_count: int = 0,
        wire_count: int = 0,
        flip_flop_count: int = 0,
        critical_path_ns: Optional[float] = None,
        slack_ns: Optional[float] = None,
        area_estimate: str = "unknown",
    ):
        self.cell_count = cell_count
        self.wire_count = wire_count
        self.flip_flop_count = flip_flop_count
        self.critical_path_ns = critical_path_ns
        self.slack_ns = slack_ns
        self.area_estimate = area_estimate

    @classmethod
    def from_dict(cls, data: dict) -> "SynthesisMetrics":
        return cls(
            cell_count=data.get("cell_count", 0),
            wire_count=data.get("wire_count", 0),
            flip_flop_count=data.get("flip_flop_count", 0),
            critical_path_ns=data.get("critical_path_ns"),
            slack_ns=data.get("slack_ns"),
            area_estimate=data.get("area_estimate", "unknown"),
        )

    def to_dict(self) -> dict:
        return {
            "cell_count": self.cell_count,
            "wire_count": self.wire_count,
            "flip_flop_count": self.flip_flop_count,
            "critical_path_ns": self.critical_path_ns,
            "slack_ns": self.slack_ns,
            "area_estimate": self.area_estimate,
        }

    def __repr__(self) -> str:
        return f"<SynthesisMetrics cells={self.cell_count} wires={self.wire_count} ff={self.flip_flop_count}>"
