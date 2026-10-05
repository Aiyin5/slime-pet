"""史莱姆身体的程序化绘制与动画。

不依赖任何图片素材：果冻身体（圆顶 + 波浪底边）、渐变、高光、眼睛、
投影全部由 QPainter 绘制。动画以时间为参数，逐帧计算：

- IDLE     待机呼吸、轻微晃动
- PRESTART 即将开始：小幅连续弹跳，身体泛黄
- ALERT    到点强提醒：剧烈连续弹跳，身体泛橙
- HAPPY    任务完成：一次性大跳，落地后回到 IDLE
- DRAG     被拖拽：垂直拉长
- SLEEP    休眠：压扁、闭眼
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient,
    QTransform,
)


class SlimeMode:
    IDLE = "idle"
    PRESTART = "prestart"
    ALERT = "alert"
    HAPPY = "happy"
    DRAG = "drag"
    SLEEP = "sleep"


# 三套调色板：(顶部, 中部, 底部, 描边)
PALETTE_GREEN = (
    QColor("#c4f7e0"), QColor("#6fe0aa"), QColor("#2fae77"), QColor("#239a68"),
)
PALETTE_YELLOW = (
    QColor("#fdf3c2"), QColor("#f7d26c"), QColor("#e2a23a"), QColor("#c98a28"),
)
PALETTE_ORANGE = (
    QColor("#ffe3ab"), QColor("#ffb15e"), QColor("#ef773a"), QColor("#d95f24"),
)


def mix_color(c1: QColor, c2: QColor, k: float) -> QColor:
    k = max(0.0, min(1.0, k))
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * k),
        int(c1.green() + (c2.green() - c1.green()) * k),
        int(c1.blue() + (c2.blue() - c1.blue()) * k),
    )


@dataclass
class _Pose:
    """一帧的形变参数。"""
    lift: float = 0.0       # 身体整体上移（像素）
    sx: float = 1.0
    sy: float = 1.0
    skew: float = 0.0       # 左右倾斜（弧度）
    palette_mix: float = 0.0  # 0 绿 → 1 暖色
    warm_target: int = 1    # 1 黄，2 橙
    blink: float = 1.0      # 1 睁眼，0 闭眼
    mouth: str = "smile"    # smile / open / bigsmile / flat
    shadow_scale: float = 1.0
    shadow_alpha: float = 1.0


class SlimeBody:
    HAPPY_DURATION = 0.95

    def __init__(self):
        self.mode = SlimeMode.IDLE
        self._happy_start = 0.0
        self._next_blink = time.monotonic() + 2.5
        self._blink_start = 0.0

    def set_mode(self, mode: str):
        if mode == SlimeMode.HAPPY:
            self._happy_start = time.monotonic()
        self.mode = mode

    def trigger_happy(self):
        self._happy_start = time.monotonic()
        self.mode = SlimeMode.HAPPY

    # ------------------------------------------------------------------ #
    # 姿态计算
    # ------------------------------------------------------------------ #
    def _blink_value(self, now: float) -> float:
        if self.mode == SlimeMode.SLEEP:
            return 0.0
        if now >= self._next_blink and self._blink_start == 0.0:
            self._blink_start = now
        if self._blink_start:
            p = (now - self._blink_start) / 0.18
            if p >= 1:
                self._blink_start = 0.0
                self._next_blink = now + 2.0 + (hash(int(now)) % 30) / 10.0
                return 1.0
            # 0→1→0 的闭合曲线
            return max(0.08, 1.0 - math.sin(p * math.pi))
        return 1.0

    def _pose(self, now: float) -> _Pose:
        pose = _Pose(blink=self._blink_value(now))

        if self.mode == SlimeMode.IDLE:
            breath = math.sin(now * 1.8) * 0.022
            pose.sx = 1 + breath
            pose.sy = 1 - breath
            pose.skew = math.sin(now * 0.9) * 0.018
            pose.mouth = "smile"

        elif self.mode == SlimeMode.SLEEP:
            pose.sx = 1.09
            pose.sy = 0.70
            pose.mouth = "flat"

        elif self.mode == SlimeMode.DRAG:
            jitter = math.sin(now * 17) * 0.012
            pose.sx = 0.90
            pose.sy = 1.12
            pose.skew = jitter
            pose.mouth = "open"

        elif self.mode == SlimeMode.PRESTART:
            t = (now % 1.15) / 1.15
            pose.lift = 26 * math.sin(math.pi * t)
            edge = min(t, 1 - t)
            landing = max(0.0, 1 - edge / 0.13)
            pose.sx = 1 + 0.13 * landing - 0.04 * (1 - landing)
            pose.sy = 1 - 0.16 * landing + 0.05 * (1 - landing)
            pose.palette_mix = 0.55 + 0.45 * landing
            pose.warm_target = 1
            pose.mouth = "open"

        elif self.mode == SlimeMode.ALERT:
            t = (now % 0.72) / 0.72
            pose.lift = 58 * math.sin(math.pi * t)
            edge = min(t, 1 - t)
            landing = max(0.0, 1 - edge / 0.12)
            pose.sx = 1 + 0.18 * landing - 0.05 * (1 - landing)
            pose.sy = 1 - 0.22 * landing + 0.07 * (1 - landing)
            pose.palette_mix = 0.75 + 0.25 * landing
            pose.warm_target = 2
            pose.mouth = "open"

        elif self.mode == SlimeMode.HAPPY:
            p = min(1.0, (now - self._happy_start) / self.HAPPY_DURATION)
            pose.lift = 74 * 4 * p * (1 - p)
            # 空中拉长，落地压扁
            landing = max(0.0, 1 - min(p, 1 - p) / 0.12) if p > 0.5 else 0.0
            airborne = math.sin(math.pi * p)
            pose.sx = 1 + 0.16 * landing - 0.05 * airborne
            pose.sy = 1 - 0.2 * landing + 0.07 * airborne
            pose.mouth = "bigsmile"
            pose.blink = 1.0
        return pose

    def happy_finished(self) -> bool:
        return (
            self.mode == SlimeMode.HAPPY
            and time.monotonic() - self._happy_start > self.HAPPY_DURATION
        )

    # ------------------------------------------------------------------ #
    # 绘制
    # ------------------------------------------------------------------ #
    def paint(self, painter: QPainter, rect: QRectF):
        now = time.monotonic()
        pose = self._pose(now)

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        w = rect.width()
        h = rect.height()
        cx = rect.center().x()
        base_y = rect.bottom()

        # ---------------- 投影 ----------------
        shadow_w = w * 0.46 * pose.sx * pose.shadow_scale
        shadow_h = h * 0.05
        lift_ratio = pose.lift / max(h, 1)
        shadow_w *= 1 - 0.35 * lift_ratio
        shadow_alpha = 0.20 * pose.shadow_alpha * (1 - 0.55 * lift_ratio)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(28, 80, 55, int(255 * shadow_alpha)))
        painter.drawEllipse(
            QRectF(cx - shadow_w / 2, base_y - shadow_h / 2 + 3,
                   shadow_w, shadow_h)
        )

        # ---------------- 颜色 ----------------
        warm = PALETTE_ORANGE if pose.warm_target == 2 else PALETTE_YELLOW
        k = pose.palette_mix
        top_c = mix_color(PALETTE_GREEN[0], warm[0], k)
        mid_c = mix_color(PALETTE_GREEN[1], warm[1], k)
        bot_c = mix_color(PALETTE_GREEN[2], warm[2], k)
        edge_c = mix_color(PALETTE_GREEN[3], warm[3], k)

        # ---------------- 身体路径（本地坐标：底中为原点） ----------------
        body = self._body_path(w, h)

        transform = QTransform()
        transform.translate(cx, base_y - pose.lift)
        transform.shear(pose.skew, 0)
        transform.scale(pose.sx, pose.sy)
        body = transform.map(body)

        # 渐变填充
        grad = QLinearGradient(0, base_y - h, 0, base_y)
        grad.setColorAt(0.0, top_c)
        grad.setColorAt(0.55, mid_c)
        grad.setColorAt(1.0, bot_c)
        painter.setBrush(grad)
        pen = QPen(edge_c, 2.2)
        painter.setPen(pen)
        painter.drawPath(body)

        # 身体内部柔和亮斑（果冻通透感）
        inner = QRadialGradient(
            QPointF(cx - w * 0.12, base_y - h * 0.72), w * 0.4
        )
        inner.setColorAt(0, QColor(255, 255, 255, 90))
        inner.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(inner)
        painter.drawPath(body)

        # ---------------- 高光 ----------------
        hl_transform = QTransform()
        hl_transform.translate(cx - pose.lift * 0 + 0, base_y - pose.lift)
        hl_transform.scale(pose.sx, pose.sy)
        self._draw_highlights(painter, w, h, transform)

        # ---------------- 五官 ----------------
        self._draw_face(painter, w, h, transform, pose, edge_c)

    @staticmethod
    def _body_path(w: float, h: float) -> QPainterPath:
        """本地坐标，原点在身体底部中心，y 向上为负。"""
        half = w / 2
        shoulder_y = -h * 0.42
        shoulder_x = half * 0.92
        wave = h * 0.045

        path = QPainterPath()
        # 底边波浪：从左到右两个波
        path.moveTo(-half, 0)
        path.cubicTo(-half * 0.66, wave, -half * 0.33, -wave, 0, 0)
        path.cubicTo(half * 0.33, wave, half * 0.66, -wave, half, 0)
        # 右侧外扩到肩
        path.quadTo(half * 1.02, h * -0.2, shoulder_x, shoulder_y)
        # 圆顶（两段三次贝塞尔）
        path.cubicTo(
            shoulder_x, -h * 0.96, w * 0.27, -h * 1.02, 0, -h
        )
        path.cubicTo(
            -w * 0.27, -h * 1.02, -shoulder_x, -h * 0.96, -shoulder_x, shoulder_y
        )
        # 左侧回到左下
        path.quadTo(-half * 1.02, h * -0.2, -half, 0)
        path.closeSubpath()
        return path

    def _draw_highlights(self, painter: QPainter, w: float, h: float,
                         transform: QTransform):
        # 大高光
        big = QRectF(-w * 0.30, -h * 0.88, w * 0.20, h * 0.16)
        big = transform.mapRect(big)
        painter.save()
        painter.translate(big.center().x(), big.center().y())
        painter.rotate(-22)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 120))
        painter.drawEllipse(QRectF(-big.width() / 2, -big.height() / 2,
                                   big.width(), big.height()))
        painter.restore()
        # 小高光
        small = QRectF(w * 0.06, -h * 0.74, w * 0.08, h * 0.07)
        small = transform.mapRect(small)
        painter.setBrush(QColor(255, 255, 255, 90))
        painter.drawEllipse(small)

    def _draw_face(self, painter: QPainter, w: float, h: float,
                   transform: QTransform, pose: _Pose, edge_c: QColor):
        eye_dx = w * 0.155
        eye_y = -h * 0.60
        ew = w * 0.075
        eh = h * 0.115 * pose.blink

        def map_pt(x, y):
            return transform.map(QPointF(x, y))

        painter.setPen(Qt.NoPen)
        for sign in (-1, 1):
            c = map_pt(sign * eye_dx, eye_y)
            if pose.blink < 0.25:
                # 闭眼：弧线
                pen = QPen(QColor("#20332a"), 2.4)
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                lx = ew * 1.3
                painter.drawArc(
                    QRectF(c.x() - lx, c.y() - 1, lx * 2, eh * 2 + 4),
                    0 * 16, 180 * 16,
                )
                painter.setPen(Qt.NoPen)
            else:
                painter.setBrush(QColor("#20332a"))
                painter.drawEllipse(QRectF(c.x() - ew, c.y() - eh, ew * 2, eh * 2))
                # 眼睛高光
                painter.setBrush(QColor(255, 255, 255, 230))
                painter.drawEllipse(
                    QRectF(c.x() - ew * 0.55, c.y() - eh * 0.75, ew * 0.62, eh * 0.62)
                )
                painter.setBrush(QColor(255, 255, 255, 160))
                painter.drawEllipse(
                    QRectF(c.x() + ew * 0.25, c.y() + eh * 0.2, ew * 0.34, eh * 0.34)
                )

        # 嘴
        mc = map_pt(0, -h * 0.46)
        pen = QPen(QColor("#20332a"), 2.4)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        mw = w * 0.10
        if pose.mouth == "smile":
            painter.drawArc(QRectF(mc.x() - mw, mc.y() - 6, mw * 2, 16),
                            180 * 16, 180 * 16)
        elif pose.mouth == "bigsmile":
            painter.setBrush(QColor("#d85b65"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(mc.x() - mw * 1.15, mc.y() - 5,
                                       mw * 2.3, h * 0.075))
            painter.setBrush(QColor(255, 255, 255, 200))
            painter.drawEllipse(QRectF(mc.x() - mw * 0.8, mc.y() + 2,
                                       mw * 1.6, h * 0.03))
        elif pose.mouth == "open":
            painter.setBrush(QColor("#7a4a3a"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(mc.x() - mw * 0.55, mc.y() - 3,
                                       mw * 1.1, h * 0.05))
        else:  # flat
            painter.drawLine(QPointF(mc.x() - mw * 0.7, mc.y() + 2),
                             QPointF(mc.x() + mw * 0.7, mc.y() + 2))
