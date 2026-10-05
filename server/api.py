"""本地 FastAPI 后台：任务 CRUD 接口 + 管理页面静态托管。

仅监听 127.0.0.1，不设密码，数据不出本机。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from core.database import Database, TaskValidationError


def create_app(db: Database, web_dir: str | Path) -> FastAPI:
    app = FastAPI(title="Slime Pet 本地后台", docs_url=None, redoc_url=None)
    web_dir = Path(web_dir)

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    @app.get("/api/tasks")
    def list_tasks(scope: str = "all", include_completed: bool = True):
        if scope not in ("all", "today"):
            raise HTTPException(status_code=400, detail="scope 只能是 all 或 today")
        tasks = db.list_tasks(scope=scope, include_completed=include_completed)
        return [t.to_dict() for t in tasks]

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: int):
        task = db.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return task.to_dict()

    @app.post("/api/tasks", status_code=201)
    def create_task(payload: dict):
        try:
            task = db.create_task(payload)
        except TaskValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return task.to_dict()

    @app.put("/api/tasks/{task_id}")
    def update_task(task_id: int, payload: dict):
        try:
            task = db.update_task(task_id, payload)
        except TaskValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return task.to_dict()

    @app.post("/api/tasks/{task_id}/complete")
    def complete_task(task_id: int):
        task = db.complete_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return task.to_dict()

    @app.delete("/api/tasks/{task_id}")
    def delete_task(task_id: int):
        if not db.delete_task(task_id):
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"ok": True}

    # ------------------------------------------------------------------ #
    # 静态管理页面
    # ------------------------------------------------------------------ #
    @app.get("/")
    def index():
        return RedirectResponse(url="/index.html")

    app.mount(
        "/",
        StaticFiles(directory=str(web_dir), html=True),
        name="web",
    )
    return app
