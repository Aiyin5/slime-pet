"""生成 1024x1024 史莱姆 PNG（供 macOS 制作 .icns；也可直接当图标）。"""
from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
libs = BASE / "libs"
if libs.exists():
    sys.path.insert(0, str(libs))

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pet.slime_render import SlimeBody  # noqa: E402

app = QApplication(sys.argv)

SIZE = 1024
pix = QPixmap(SIZE, SIZE)
pix.fill(Qt.transparent)
p = QPainter(pix)
p.setRenderHint(QPainter.Antialiasing, True)
p.setRenderHint(QPainter.SmoothPixmapTransform, True)

body = SlimeBody()
body.paint(p, QRectF(96, 60, 832, 900))
p.end()

out = BASE / "assets" / "slime_1024.png"
out.parent.mkdir(exist_ok=True)
pix.save(str(out), "PNG")
print("saved", out)
