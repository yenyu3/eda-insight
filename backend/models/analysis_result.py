from __future__ import annotations

from typing import Optional, Any


class AnalysisResult:
    """
    一次 run 的完整分析結果，對應 GET /api/result/<run_id> 的回應格式。

    這個類別主要作為：
    - DB 資料與 API response 的中介層
    - 前後端共享 schema 的單一來源
    """

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
    def lint_issues(self) -> list[dict]:
        """從 parser_result 直接取出 lint_issues 列表。"""
        return (self.parser_result or {}).get("lint_issues", [])

    @property
    def modules(self) -> list[dict]:
        """從 parser_result 直接取出 modules 列表。"""
        return (self.parser_result or {}).get("modules", [])

    def to_dict(self) -> dict[str, Any]:
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

    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisResult":
        """
        從 dict 反序列化成 AnalysisResult。

        支援資料來源：
        - DB 讀出的 dict
        - API response dict
        - 測試資料 dict
        """
        return cls(
            run_id=data.get("run_id", ""),
            filename=data.get("filename", ""),
            parser_result=data.get("parser_result"),
            workflow_plan=data.get("workflow_plan"),
            waveform=data.get("waveform"),
            synthesis=data.get("synthesis"),
            dependency_graph=data.get("dependency_graph"),
            ai_summary=data.get("ai_summary"),
            risk_scores=data.get("risk_scores"),
            bottleneck_analysis=data.get("bottleneck_analysis"),
            flowchart=data.get("flowchart"),
        )

    def __repr__(self) -> str:
        return (
            f"<AnalysisResult run={self.run_id[:8]} "
            f"modules={len(self.modules)} lint={len(self.lint_issues)}>"
        )


class SynthesisMetrics:
    """
    合成階段的 PPA 指標，對應 Yosys 輸出。

    欄位語意：
    - cell_count: cell 數量
    - wire_count: wire / net 數量（heuristic）
    - flip_flop_count: flip-flop 數量
    - critical_path_ns: 臨界路徑時間（ns）
    - slack_ns: slack（ns）
    - area_estimate: 粗略面積估計分類
    """

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
    def from_dict(cls, data: Optional[dict]) -> "SynthesisMetrics":
        if not data:
            return cls()

        return cls(
            cell_count=data.get("cell_count", 0),
            wire_count=data.get("wire_count", 0),
            flip_flop_count=data.get("flip_flop_count", 0),
            critical_path_ns=data.get("critical_path_ns"),
            slack_ns=data.get("slack_ns"),
            area_estimate=data.get("area_estimate", "unknown"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_count": self.cell_count,
            "wire_count": self.wire_count,
            "flip_flop_count": self.flip_flop_count,
            "critical_path_ns": self.critical_path_ns,
            "slack_ns": self.slack_ns,
            "area_estimate": self.area_estimate,
        }

    def __repr__(self) -> str:
        return (
            f"<SynthesisMetrics cells={self.cell_count} "
            f"wires={self.wire_count} ff={self.flip_flop_count}>"
        )
