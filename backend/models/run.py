from __future__ import annotations

from typing import Optional, Any
from datetime import datetime, timezone


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
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

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
        """
        從 db_manager.get_run() 回傳的 dict 建立 Run 物件。

        這裡採明確 mapping，避免依賴 __init__ 的內部實作。
        """
        return cls._from_mapping(row)

    @classmethod
    def from_dict(cls, data: dict) -> "Run":
        """
        從一般 dict 建立 Run 物件。
        可用於測試、API data、或未來序列化流程。
        """
        return cls._from_mapping(data)

    @classmethod
    def _from_mapping(cls, data: dict) -> "Run":
        return cls(
            run_id=data.get("run_id", ""),
            filename=data.get("filename", ""),
            status=data.get("status", "pending"),
            created_at=data.get("created_at"),
            verilog_content=data.get("verilog_content"),
            design_content=data.get("design_content"),
            parser_result=data.get("parser_result"),
            workflow_plan=data.get("workflow_plan"),
            sim_result=data.get("sim_result"),
            synthesis_result=data.get("synthesis_result"),
            dependency_graph=data.get("dependency_graph"),
            ai_summary=data.get("ai_summary"),
            risk_scores=data.get("risk_scores"),
            bottleneck_analysis=data.get("bottleneck_analysis"),
            ppa_cell_count=data.get("ppa_cell_count"),
            ppa_critical_path_ns=data.get("ppa_critical_path_ns"),
            ppa_slack_ns=data.get("ppa_slack_ns"),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        序列化為 API JSON-compatible dict（不含大型 content 欄位）。

        用途：
        - 列表頁
        - history
        - status polling
        - 一般摘要顯示
        """
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

    def full_dict(self) -> dict[str, Any]:
        """
        序列化為包含大型 content 的完整 dict。

        用途：
        - 需要完整設計內容的 debug
        - 特定分析 route
        """
        data = self.to_dict()
        data.update({
            "verilog_content": self.verilog_content,
            "design_content": self.design_content,
        })
        return data

    def __repr__(self) -> str:
        return f"<Run {self.run_id[:8]} file={self.filename!r} status={self.status!r}>"
