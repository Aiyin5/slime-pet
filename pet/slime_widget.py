"""桌面宠物主窗口：透明置顶的史莱姆 + 待办气泡 + 交互。

交互：
- 左键单击  切换到下一个待办（同时关闭当前提醒）
- 左键双击  当前任务标记完成（史莱姆开心跳一下）
- 拖动      移动位置
- 右键      菜单（管理页面 / 暂停提醒 / 显隐 / 退出）
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QAction, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QApplication, QMenu, QSystemTrayIcon, QWidget,
)

from core.database import Database
from core.models import Task, TaskStatus

from .slime_render import SlimeBody, SlimeMode

WINDOW_W = 272
WINDOW_H = 330
BODY_H = 196
BODY_TOP = WINDOW_H - BODY_H - 6
DRAG_THRESHOLD = 4


def _pad(n: int) -> str:
    return f"{n:02d}"


def fmt_task_time(task: Task) -> str:
    s, e = task.start_time, task.end_time
    if s.date() == e.date():
        return f"{_pad(s.month)}-{_pad(s.day)} {_pad(s.hour)}:{_pad(s.minute)}" \
               f" ~ {_pad(e.hour)}:{_pad(s.minute)}"
    return (
        f"{_pad(s.month)}-{_pad(s.day)} {_pad(s.hour)}:{_pad(s.minute)} → "
        f"{_pad(e.month)}-{_pad(e.day)} {_pad(e.hour)}:{_pad(e.minute)}"
    )


def human_hint(task: Task) -> str:
    now = datetime.now()
    if task.status == TaskStatus.PENDING:
        mins = int((task.start_time - now).total_seconds() // 60)
        if mins <= 0:
            return "马上开始"
        if mins < 60:
            return f"{mins} 分钟后开始"
        if mins < 60 * 24:
            return f"{mins // 60} 小时 {mins % 60} 分后开始"
        return f"{mins // 1440} 天 {mins % 1440 // 60} 小时后开始"
    if task.status == TaskStatus.IN_PROGRESS:
        mins = int((task.end_time - now).total_seconds() // 60)
        if mins <= 0:
            return "进行中 · 即将结束"
        if mins < 60:
            return f"进行中 · 剩余 {mins} 分钟"
        return f"进行中 · 剩余 {mins // 60} 小时 {mins % 60} 分"
    if task.status == TaskStatus.EXPIRED:
        return "已到结束时间 · 双击我完成"
    return ""


class SlimePetWindow(QWidget):
    def __init__(self, db: Database, open_admin_callback, quit_callback):
        super().__init__()
        self.db = db
        self._open_admin = open_admin_callback
        self._quit = quit_callback
        self.muted = False

        self.setWindowTitle("史莱姆桌面宠物")
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(WINDOW_W, WINDOW_H)

        self.body = SlimeBody()
        self.tasks: list[Task] = []
        self.index = 0
        self._reminder_task_id: int | None = None
        self._dismiss = None  # 由调度引擎注入：单击后抑制当前阶段提醒

        # 鼠标状态
        self._press_pos: QPoint | None = None
        self._win_offset: QPoint | None = None
        self._dragging = False

        # 动画刷新
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._on_frame)
        self._timer.start()

        self.tray = SlimeTray(self, open_admin_callback, quit_callback)
        self.tray.show()

        self.refresh_tasks()
        self._place_near_bottom_right()

    # ------------------------------------------------------------------ #
    # 位置与任务数据
    # ------------------------------------------------------------------ #
    def _place_near_bottom_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - WINDOW_W - 40
        y = screen.bottom() - WINDOW_H + 18
        self.move(x, y)

    def refresh_tasks(self, focus_task_id: int | None = None):
        self.tasks = self.db.active_tasks()
        if not self.tasks:
            self.index = 0
            return
        ids = [t.id for t in self.tasks]
        if focus_task_id is not None and focus_task_id in ids:
            self.index = ids.index(focus_task_id)
        else:
            self.index = min(self.index, len(self.tasks) - 1)
            if self.index < 0:
                self.index = self._default_index()

    def _default_index(self) -> int:
        """默认关注：进行中 → 最早待开始 → 第一个。"""
        for i, t in enumerate(self.tasks):
            if t.status == TaskStatus.IN_PROGRESS:
                return i
        for i, t in enumerate(self.tasks):
            if t.status == TaskStatus.PENDING:
                return i
        return 0

    def current_task(self) -> Task | None:
        if not self.tasks:
            return None
        return self.tasks[self.index]

    # ------------------------------------------------------------------ #
    # 调度引擎接口
    # ------------------------------------------------------------------ #
    def show_reminder(self, mode: str, task_id: int):
        if self.muted:
            return
        self.refresh_tasks(focus_task_id=task_id)
        self._reminder_task_id = task_id
        self.body.set_mode(mode)
        self.raise_()

    def clear_reminder(self):
        self._reminder_task_id = None
        if self.body.mode in (SlimeMode.ALERT, SlimeMode.PRESTART):
            self.body.set_mode(SlimeMode.IDLE)

    def set_muted(self, muted: bool):
        self.muted = muted
        if muted:
            self.clear_reminder()

    # ------------------------------------------------------------------ #
    # 帧刷新
    # ------------------------------------------------------------------ #
    def _on_frame(self):
        if self.body.happy_finished():
            self.body.set_mode(SlimeMode.IDLE)
        self.update()

    # ------------------------------------------------------------------ #
    # 绘制
    # ------------------------------------------------------------------ #
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        task = self.current_task()
        if task:
            bubble = QRectF(12, 10, WINDOW_W - 24, 96)
        else:
            bubble = QRectF(26, 18, WINDOW_W - 52, 64)
        self._paint_bubble(painter, bubble, task)

        # 史莱姆身体
        body_rect = QRectF(30, BODY_TOP, WINDOW_W - 60, BODY_H)
        self.body.paint(painter, body_rect)
        painter.end()

    def _paint_bubble(self, painter: QPainter, rect: QRectF,
                      task: Task | None):
        tip_w, tip_h = 18.0, 11.0
        tip_x = rect.center().x()

        path = QPainterPath()
        radius = 16.0
        path.moveTo(rect.left() + radius, rect.top())
        path.lineTo(rect.right() - radius, rect.top())
        path.arcTo(QRectF(rect.right() - 2 * radius, rect.top(),
                          2 * radius, 2 * radius), 90, -90)
        path.lineTo(rect.right(), rect.bottom() - radius)
        path.arcTo(QRectF(rect.right() - 2 * radius,
                          rect.bottom() - 2 * radius,
                          2 * radius, 2 * radius), 0, -90)
        # 底边到尖角右侧
        path.lineTo(tip_x + tip_w / 2, rect.bottom())
        path.lineTo(tip_x, rect.bottom() + tip_h)
        path.lineTo(tip_x - tip_w / 2, rect.bottom())
        path.lineTo(rect.left() + radius, rect.bottom())
        path.arcTo(QRectF(rect.left(), rect.bottom() - 2 * radius,
                          2 * radius, 2 * radius), -90, -90)
        path.lineTo(rect.left(), rect.top() + radius)
        path.arcTo(QRectF(rect.left(), rect.top(), 2 * radius, 2 * radius),
                   180, -90)
        path.closeSubpath()

        painter.setPen(QPen(QColor(210, 226, 218), 1.2))
        painter.setBrush(QColor(255, 255, 255, 248))
        painter.drawPath(path)

        text_left = rect.left() + 16
        text_w = rect.width() - 32

        if task is None:
            no_title = QFont("Microsoft YaHei", 11)
            no_title.setBold(True)
            painter.setFont(no_title)
            painter.setPen(QColor("#33443b"))
            painter.drawText(
                QRectF(text_left, rect.top() + 10, text_w, 22),
                Qt.AlignLeft | Qt.AlignVCenter, "暂无待办",
            )
            painter.setFont(QFont("Microsoft YaHei", 9))
            painter.setPen(QColor("#8aa095"))
            painter.drawText(
                QRectF(text_left, rect.top() + 33, text_w, 20),
                Qt.AlignLeft | Qt.AlignVCenter, "右键我 → 打开管理页面",
            )
            return

        # 左侧任务色条
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(task.color))
        painter.drawRoundedRect(
            QRectF(rect.left() + 8, rect.top() + 12, 5, rect.height() - 26),
            2.5, 2.5,
        )

        # 标题（省略）
        title_font = QFont("Microsoft YaHei", 11)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#26352d"))
        fm = painter.fontMetrics()
        title = fm.elidedText(task.title, Qt.ElideRight, int(text_w - 30))
        painter.drawText(
            QRectF(text_left + 8, rect.top() + 9, text_w - 8, 24),
            Qt.AlignLeft | Qt.AlignVCenter, title,
        )

        # 时间
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(QColor("#5d7268"))
        painter.drawText(
            QRectF(text_left + 8, rect.top() + 34, text_w - 8, 20),
            Qt.AlignLeft | Qt.AlignVCenter, fmt_task_time(task),
        )

        # 状态提示 + 角标
        painter.setPen(QColor("#26b578"))
        painter.drawText(
            QRectF(text_left + 8, rect.top() + 57, text_w - 52, 22),
            Qt.AlignLeft | Qt.AlignVCenter, human_hint(task),
        )
        painter.setPen(QColor("#9db3a8"))
        painter.drawText(
            QRectF(rect.right() - 48, rect.top() + 57, 40, 22),
            Qt.AlignRight | Qt.AlignVCenter,
            f"{self.index + 1}/{len(self.tasks)}",
        )

    # ------------------------------------------------------------------ #
    # 鼠标交互
    # ------------------------------------------------------------------ #
    def _in_body(self, pos: QPoint) -> bool:
        return QRectF(20, BODY_TOP - 10, WINDOW_W - 40, BODY_H + 16).contains(
            pos.x(), pos.y()
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._in_body(event.position().toPoint()):
            self._press_pos = event.globalPosition().toPoint()
            self._win_offset = self._press_pos - self.frameGeometry().topLeft()
            self._dragging = False

    def mouseMoveEvent(self, event):
        if self._press_pos is None:
            return
        global_pos = event.globalPosition().toPoint()
        if not self._dragging and (
            (global_pos - self._press_pos).manhattanLength() >= DRAG_THRESHOLD
        ):
            self._dragging = True
            self.body.set_mode(SlimeMode.DRAG)
        if self._dragging:
            self.move(global_pos - self._win_offset)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self._press_pos is None:
            return
        was_dragging = self._dragging
        self._press_pos = None
        if was_dragging:
            # 恢复提醒/待机状态
            if self._reminder_task_id is not None:
                task = self.db.get_task(self._reminder_task_id)
                if task:
                    self.body.set_mode(
                        SlimeMode.ALERT
                        if task.status in (TaskStatus.IN_PROGRESS, TaskStatus.EXPIRED)
                        else SlimeMode.PRESTART
                    )
            else:
                self.body.set_mode(SlimeMode.IDLE)
        else:
            self._on_click_body()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self._in_body(event.position().toPoint()):
            task = self.current_task()
            if task:
                self.db.complete_task(task.id)
                self._reminder_task_id = None
                self.refresh_tasks()
                self.body.trigger_happy()

    def _on_click_body(self):
        """单击：浏览下一个待办，并视为对当前提醒的回应。"""
        current = self.current_task()
        self._reminder_task_id = None
        if self._dismiss and current:
            self._dismiss(current.id)
        if self.tasks:
            self.index = (self.index + 1) % len(self.tasks)
        self.body.set_mode(SlimeMode.IDLE)

    # ------------------------------------------------------------------ #
    # 右键菜单
    # ------------------------------------------------------------------ #
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        act_admin = QAction("打开任务管理页面", self)
        act_admin.triggered.connect(self._open_admin)
        menu.addAction(act_admin)

        act_mute = QAction(
            "恢复提醒" if self.muted else "暂停提醒", self
        )
        act_mute.triggered.connect(lambda: self.set_muted(not self.muted))
        menu.addAction(act_mute)

        menu.addSeparator()
        act_hide = QAction("隐藏史莱姆", self)
        act_hide.triggered.connect(self.hide)
        menu.addAction(act_hide)

        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        menu.exec(event.globalPos())


# ---------------------------------------------------------------------- #
# 系统托盘
# ---------------------------------------------------------------------- #
def _make_tray_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#6fe0aa"))
    p.setPen(QPen(QColor("#239a68"), 2))
    path = QPainterPath()
    path.moveTo(8, 54)
    path.quadTo(8, 10, 32, 8)
    path.quadTo(56, 10, 56, 54)
    path.cubicTo(46, 48, 40, 58, 32, 54)
    path.cubicTo(24, 50, 18, 58, 8, 54)
    path.closeSubpath()
    p.drawPath(path)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#20332a"))
    p.drawEllipse(22, 28, 6, 9)
    p.drawEllipse(36, 28, 6, 9)
    p.end()
    return QIcon(pix)


class SlimeTray(QSystemTrayIcon):
    def __init__(self, window: SlimePetWindow, open_admin, quit_app):
        super().__init__(_make_tray_icon(), parent=window)
        self.window = window
        menu = QMenu()
        act_admin = QAction("打开任务管理页面")
        act_admin.triggered.connect(open_admin)
        menu.addAction(act_admin)

        act_show = QAction("显示 / 隐藏史莱姆")
        act_show.triggered.connect(self._toggle_visible)
        menu.addAction(act_show)

        menu.addSeparator()
        act_quit = QAction("退出")
        act_quit.triggered.connect(quit_app)
        menu.addAction(act_quit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)
        self.setToolTip("史莱姆桌面宠物")

    def _toggle_visible(self):
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._toggle_visible()
