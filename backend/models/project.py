"""
models/project.py — Project 資料模型

代表一個「分析專案」的概念，
可以把多個 Run 組織成一個有名稱的分析任務。
（目前為預留設計，未來可擴充至資料庫層）
"""

from __future__ import annotations
from typing import Optional
import uuid


class Project:
    """代表一個 EDA 分析專案，包含多個 Run。"""

    def __init__(
        self,
        name: str,
        project_id: Optional[str] = None,
        description: Optional[str] = None,
        created_at: Optional[str] = None,
        run_ids: Optional[list[str]] = None,
    ):
        self.project_id = project_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.created_at = created_at
        self.run_ids: list[str] = run_ids or []

    def add_run(self, run_id: str) -> None:
        """將 run_id 加入此專案。"""
        if run_id not in self.run_ids:
            self.run_ids.append(run_id)

    def remove_run(self, run_id: str) -> None:
        """從此專案移除 run_id。"""
        self.run_ids = [r for r in self.run_ids if r != run_id]

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        return cls(
            name=data["name"],
            project_id=data.get("project_id"),
            description=data.get("description"),
            created_at=data.get("created_at"),
            run_ids=data.get("run_ids", []),
        )

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "run_ids": self.run_ids,
            "run_count": len(self.run_ids),
        }

    def __repr__(self) -> str:
        return f"<Project {self.project_id[:8]} name={self.name!r} runs={len(self.run_ids)}>"
