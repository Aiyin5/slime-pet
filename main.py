"""史莱姆桌面宠物 · 程序入口。

主线程运行 PySide6 桌面宠物；FastAPI 后台在守护线程中运行，
监听 127.0.0.1:17821，提供任务接口与管理页面。
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

# 路径区分：
# - 开发环境：资源与可写数据都在项目目录，依赖在项目内 libs
# - PyInstaller 打包后：静态资源在解压目录 sys._MEIPASS（只读），
#   可写的数据库放在 exe 同级目录，保证持久化与可写。
FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    BASE_DIR = Path(sys.executable).resolve().parent
    RES_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent
    RES_DIR = BASE_DIR
    LIBS = BASE_DIR / "libs"
    if LIBS.exists() and str(LIBS) not in sys.path:
        sys.path.insert(0, str(LIBS))

import uvicorn
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from core.database import Database
from core.scheduler import ReminderScheduler
from pet.slime_widget import SlimePetWindow
from server.api import create_app

PORT = 17821


def main():
    db = Database(BASE_DIR / "data" / "tasks.db")
    web_app = create_app(db, RES_DIR / "web")

    # ---------------- 后台 HTTP 服务（守护线程） ----------------
    # log_config=None：禁用 uvicorn 日志初始化。
    # windowed/无控制台打包时 sys.stdout 为 None，默认日志配置会崩溃。
    config = uvicorn.Config(
        web_app, host="127.0.0.1", port=PORT,
        log_level="warning", log_config=None,
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # 非主线程不能注册信号
    threading.Thread(target=server.run, daemon=True).start()

    # ---------------- Qt 宠物（主线程） ----------------
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)  # 关闭窗口后靠托盘常驻

    def open_admin():
        QDesktopServices.openUrl(QUrl(f"http://127.0.0.1:{PORT}/"))

    def quit_app():
        server.should_exit = True
        qt_app.quit()

    window = SlimePetWindow(db, open_admin, quit_app)

    scheduler = ReminderScheduler(db, window)
    window._dismiss = scheduler.dismiss
    scheduler.start()

    window.show()

    # 首次启动（还没有任何任务）时自动打开管理页面，方便添加第一个任务
    if not db.list_tasks():
        QTimer_single_shot(open_admin)

    sys.exit(qt_app.exec())


def QTimer_single_shot(callback):
    from PySide6.QtCore import QTimer
    QTimer.singleShot(600, callback)


if __name__ == "__main__":
    main()
