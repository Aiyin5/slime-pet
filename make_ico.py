"""生成 Windows 用的 assets/slime.ico（PyInstaller 打包前运行）。

图标由 SlimeBody 程序化绘制，无需图片素材，
因此 CI 环境可直接生成，仓库不必存放二进制图标。
"""
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

SIZE = 256
pix = QPixmap(SIZE, SIZE)
pix.fill(Qt.transparent)
p = QPainter(pix)
p.setRenderHint(QPainter.Antialiasing, True)
p.setRenderHint(QPainter.SmoothPixmapTransform, True)

body = SlimeBody()
body.paint(p, QRectF(12, 8, 232, 240))
p.end()

out = BASE / "assets" / "slime.ico"
out.parent.mkdir(exist_ok=True)
pix.save(str(out), "ICO")
print("saved", out)
