"""
models/run.py — Run 執行紀錄資料模型

對應 db_manager 的 runs 資料表結構。
提供 from_db_row() 從 DB dict 建立、to_dict() 序列化為 API JSON。
"""

from __future__ import annotations
from typing import Optional


class Run:
    """代表一次完整的 EDA pipeline 執行紀錄。"""

    def __init__(
        self,
        run_id: str,
        filename: str,
        status: str = "pending",
        created_at: Optional[str] = None,
        verilog_content: Optional[str] = None,
        design_content: Optional[str] = None,
        parser_result: Optional[dict] = None,
        workflow_plan: Optional[dict] = None,
        sim_result: Optional[dict] = None,
        synthesis_result: Optional[dict] = None,
        dependency_graph: Optional[dict] = None,
        ai_summary: Optional[str] = None,
        risk_scores: Optional[dict] = None,
        bottleneck_analysis: Optional[dict] = None,
        ppa_cell_count: Optional[int] = None,
        ppa_critical_path_ns: Optional[float] = None,
        ppa_slack_ns: Optional[float] = None,
    ):
        self.run_id = run_id
        self.filename = filename
        self.status = status
        self.created_at = created_at
        self.verilog_content = verilog_content
        self.design_content = design_content
        self.parser_result = parser_result
        self.workflow_plan = workflow_plan
        self.sim_result = sim_result
        self.synthesis_result = synthesis_result
        self.dependency_graph = dependency_graph
        self.ai_summary = ai_summary
        self.risk_scores = risk_scores
        self.bottleneck_analysis = bottleneck_analysis
        self.ppa_cell_count = ppa_cell_count
        self.ppa_critical_path_ns = ppa_critical_path_ns
        self.ppa_slack_ns = ppa_slack_ns

    @classmethod
    def from_db_row(cls, row: dict) -> "Run":
        """從 db_manager.get_run() 回傳的 dict 建立 Run 物件。"""
        return cls(**{k: row.get(k) for k in cls.__init__.__code__.co_varnames[1:] if k in row})

    def to_dict(self) -> dict:
        """序列化為 API JSON-compatible dict（不含大型 content 欄位）。"""
        return {
            "run_id": self.run_id,
            "filename": self.filename,
            "status": self.status,
            "created_at": self.created_at,
            "parser_result": self.parser_result,
            "workflow_plan": self.workflow_plan,
            "sim_result": self.sim_result,
            "synthesis_result": self.synthesis_result,
            "dependency_graph": self.dependency_graph,
            "ai_summary": self.ai_summary,
            "risk_scores": self.risk_scores,
            "bottleneck_analysis": self.bottleneck_analysis,
            "ppa_cell_count": self.ppa_cell_count,
            "ppa_critical_path_ns": self.ppa_critical_path_ns,
            "ppa_slack_ns": self.ppa_slack_ns,
        }

    def __repr__(self) -> str:
        return f"<Run {self.run_id[:8]} file={self.filename!r} status={self.status!r}>"
