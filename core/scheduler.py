"""提醒调度引擎。

QTimer 每 5 秒轮询一次任务，按时间窗口产生三类一次性事件：

- prestart  now ∈ [start - remind_before, start)  → 小幅弹跳（泛黄）
- start     now ∈ [start, end)                    → 剧烈弹跳（泛橙）
- end       now ≥ end                             → 剧烈弹跳（泛橙）

每个任务的每个阶段只触发一次；用户单击史莱姆视为「知道了」，
对应阶段被标记为已处理，不再重复打扰。纯 datetime 比较，
跨天任务无需任何特殊处理。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QTimer

from pet.slime_render import SlimeMode

from .database import Database
from .models import Task, TaskStatus


class ReminderScheduler:
    TICK_MS = 5000

    def __init__(self, db: Database, widget):
        self.db = db
        self.widget = widget
        self.fired: dict[int, set[str]] = {}
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)

    def start(self):
        self.timer.start(self.TICK_MS)
        self.tick()

    # ------------------------------------------------------------------ #
    def dismiss(self, task_id: int):
        """用户单击浏览/回应后，抑制该任务当前阶段的提醒。"""
        task = self.db.get_task(task_id)
        if task is None or task.status.value == "completed":
            return
        now = datetime.now()
        stage = self._stage_of(task, now)
        if stage:
            self.fired.setdefault(task_id, set()).add(stage)

    @staticmethod
    def _stage_of(task: Task, now: datetime) -> str | None:
        if now < task.start_time:
            return "prestart"
        if now < task.end_time:
            return "start"
        return "end"

    # ------------------------------------------------------------------ #
    def tick(self):
        now = datetime.now()
        tasks = self.db.active_tasks()
        self.widget.refresh_tasks()
        self._cleanup_stale_reminder()

        # (优先级数字越小越强, mode, task_id, stage)
        events: list[tuple[int, str, int, str]] = []

        for task in tasks:
            fired_set = self.fired.setdefault(task.id, set())
            prestart_at = task.start_time - timedelta(minutes=task.remind_before)

            if (
                task.remind_before > 0
                and prestart_at <= now < task.start_time
                and "prestart" not in fired_set
            ):
                events.append((3, SlimeMode.PRESTART, task.id, "prestart"))

            if (
                task.start_time <= now < task.end_time
                and "start" not in fired_set
            ):
                events.append((1, SlimeMode.ALERT, task.id, "start"))

            if now >= task.end_time and "end" not in fired_set:
                events.append((2, SlimeMode.ALERT, task.id, "end"))

        if not events:
            return

        events.sort(key=lambda e: e[0])
        _, mode, task_id, stage = events[0]
        self.fired[task_id].add(stage)
        self.widget.show_reminder(mode, task_id)
        return

    def _cleanup_stale_reminder(self):
        """触发提醒的任务若已被删除或完成，停止残留的提醒动画。"""
        rid = self.widget._reminder_task_id
        if rid is None:
            return
        task = self.db.get_task(rid)
        if task is None or task.status == TaskStatus.COMPLETED:
            self.widget.clear_reminder()
