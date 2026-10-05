"""任务数据模型与状态定义。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"          # 待开始
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"      # 已完成
    EXPIRED = "expired"          # 已过期（到了结束时间仍未完成）

    @property
    def label(self) -> str:
        return {
            TaskStatus.PENDING: "待开始",
            TaskStatus.IN_PROGRESS: "进行中",
            TaskStatus.COMPLETED: "已完成",
            TaskStatus.EXPIRED: "已过期",
        }[self]


@dataclass
class Task:
    id: int
    title: str
    start_time: datetime
    end_time: datetime
    status: TaskStatus
    remind_before: int = 5
    color: str = "#5ed49a"
    note: str = ""
    created_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "status": self.status.value,
            "status_label": self.status.label,
            "remind_before": self.remind_before,
            "color": self.color,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def parse_dt(value: str) -> datetime:
    """解析前端 datetime-local / ISO 字符串为本地 naive datetime。"""
    if not value:
        raise ValueError("时间不能为空")
    text = value.strip().replace("Z", "")
    # 兼容 "2026-10-05T14:00" 与带秒/毫秒的 ISO
    if len(text) == 16:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
