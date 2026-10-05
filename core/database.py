"""SQLite 数据访问层。

时间均以本地 naive datetime 的 ISO 字符串存储；一次性任务天然支持跨天
（start_time 与 end_time 为完整日期时间，结束时间可晚于次日零点）。
所有方法每次调用都使用短连接，配合 WAL 模式，方便 Qt 线程与
FastAPI 工作线程并发访问。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import Task, TaskStatus, parse_dt

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT    NOT NULL,
    start_time    TEXT    NOT NULL,
    end_time      TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'pending',
    remind_before INTEGER NOT NULL DEFAULT 5,
    color         TEXT    NOT NULL DEFAULT '#5ed49a',
    note          TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL
);
"""


class TaskValidationError(ValueError):
    """任务字段校验失败。"""


class Database:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # ------------------------------------------------------------------ #
    # 映射
    # ------------------------------------------------------------------ #
    @staticmethod
    def _compute_status(stored: str, start: datetime, end: datetime,
                        now: datetime) -> TaskStatus:
        if stored == TaskStatus.COMPLETED.value:
            return TaskStatus.COMPLETED
        if now < start:
            return TaskStatus.PENDING
        if now < end:
            return TaskStatus.IN_PROGRESS
        return TaskStatus.EXPIRED

    def _row_to_task(self, row: sqlite3.Row, now: datetime | None = None) -> Task:
        now = now or datetime.now()
        start = datetime.fromisoformat(row["start_time"])
        end = datetime.fromisoformat(row["end_time"])
        status = self._compute_status(row["status"], start, end, now)
        return Task(
            id=row["id"],
            title=row["title"],
            start_time=start,
            end_time=end,
            status=status,
            remind_before=row["remind_before"],
            color=row["color"],
            note=row["note"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #
    def list_tasks(self, scope: str = "all",
                   include_completed: bool = True) -> list[Task]:
        now = datetime.now()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY start_time ASC, id ASC"
            ).fetchall()
        tasks = [self._row_to_task(r, now) for r in rows]
        if not include_completed:
            tasks = [t for t in tasks if t.status != TaskStatus.COMPLETED]
        if scope == "today":
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            tasks = [
                t for t in tasks
                if t.start_time < day_end and t.end_time >= day_start
            ]
        return tasks

    def get_task(self, task_id: int) -> Task | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return self._row_to_task(row) if row else None

    def active_tasks(self) -> list[Task]:
        """宠物使用：所有未完成任务，按开始时间排序。"""
        return self.list_tasks(scope="all", include_completed=False)

    # ------------------------------------------------------------------ #
    # 写入
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate(data: dict[str, Any]) -> tuple[str, datetime, datetime, int, str, str]:
        title = (data.get("title") or "").strip()
        if not title:
            raise TaskValidationError("任务名称不能为空")
        try:
            start = parse_dt(data.get("start_time", ""))
            end = parse_dt(data.get("end_time", ""))
        except (ValueError, TypeError) as exc:
            raise TaskValidationError(f"时间格式不正确：{exc}") from exc
        if end <= start:
            raise TaskValidationError("结束时间必须晚于开始时间")
        try:
            remind_before = int(data.get("remind_before", 5))
        except (TypeError, ValueError):
            remind_before = 5
        remind_before = max(0, min(remind_before, 1440))
        color = (data.get("color") or "#5ed49a").strip() or "#5ed49a"
        note = (data.get("note") or "").strip()
        return title, start, end, remind_before, color, note

    def create_task(self, data: dict[str, Any]) -> Task:
        title, start, end, remind_before, color, note = self._validate(data)
        created = datetime.now()
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO tasks
                   (title, start_time, end_time, status, remind_before,
                    color, note, created_at)
                   VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)""",
                (title, start.isoformat(), end.isoformat(), remind_before,
                 color, note, created.isoformat()),
            )
            task_id = cur.lastrowid
        task = self.get_task(task_id)
        assert task is not None
        return task

    def update_task(self, task_id: int, data: dict[str, Any]) -> Task | None:
        existing = self.get_task(task_id)
        if existing is None:
            return None
        merged = {
            "title": data.get("title", existing.title),
            "start_time": data.get("start_time", existing.start_time.isoformat()),
            "end_time": data.get("end_time", existing.end_time.isoformat()),
            "remind_before": data.get("remind_before", existing.remind_before),
            "color": data.get("color", existing.color),
            "note": data.get("note", existing.note),
        }
        title, start, end, remind_before, color, note = self._validate(merged)
        with self._connect() as conn:
            conn.execute(
                """UPDATE tasks SET title=?, start_time=?, end_time=?,
                   remind_before=?, color=?, note=? WHERE id=?""",
                (title, start.isoformat(), end.isoformat(), remind_before,
                 color, note, task_id),
            )
        return self.get_task(task_id)

    def complete_task(self, task_id: int) -> Task | None:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE tasks SET status='completed' WHERE id=?", (task_id,)
            )
            if cur.rowcount == 0:
                return None
        return self.get_task(task_id)

    def delete_task(self, task_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            return cur.rowcount > 0
