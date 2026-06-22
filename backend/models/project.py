from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone
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
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.run_ids: list[str] = self._dedupe_runs(run_ids or [])

    @staticmethod
    def _dedupe_runs(run_ids: list[str]) -> list[str]:
        """去除重複 run_id，並保留原始順序。"""
        return list(dict.fromkeys(run_ids))

    @property
    def run_count(self) -> int:
        """目前專案包含的 Run 數量。"""
        return len(self.run_ids)

    def add_run(self, run_id: str) -> None:
        """將 run_id 加入此專案。"""
        if run_id not in self.run_ids:
            self.run_ids.append(run_id)

    def remove_run(self, run_id: str) -> bool:
        """
        從此專案移除 run_id。

        回傳:
            True  = 有移除
            False = 原本就不存在
        """
        if run_id not in self.run_ids:
            return False
        self.run_ids = [r for r in self.run_ids if r != run_id]
        return True

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        """
        從 dict 建立 Project。

        支援資料來源：
        - DB 讀出資料
        - API response
        - 測試資料
        """
        return cls(
            name=data.get("name", ""),
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
            "run_count": self.run_count,
        }

    def __repr__(self) -> str:
        return f"<Project {self.project_id[:8]} name={self.name!r} runs={len(self.run_ids)}>"
