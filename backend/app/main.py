"""
FastAPI 应用入口。

- 启用 CORS（开发期允许所有来源）
- 注册 settings / llm / amap 三个路由
- 启动时确保 config.json 存在
- 挂载 frontend/ 目录到 /
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.amap import router as amap_router
from .api.llm import router as llm_router
from .api.settings import router as settings_router
from .config import ensure_config_file

# UTF-8 输出（Windows 终端）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("app.main")

BASE_DIR: Path = Path(__file__).resolve().parent.parent
FRONTEND_DIR: Path = BASE_DIR.parent / "frontend"

app = FastAPI(
    title="AI 旅游小助手 后端",
    version="1.0.0",
    description="FastAPI + OpenAI 兼容 LLM + 高德地图 REST API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    ensure_config_file()
    logger.info("配置已就绪: %s", BASE_DIR / "data" / "config.json")
    logger.info("前端目录: %s (存在=%s)", FRONTEND_DIR, FRONTEND_DIR.exists())


# 注册路由
app.include_router(settings_router)
app.include_router(llm_router)
app.include_router(amap_router)


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "ai-travel-backend"}


# 挂载前端静态资源（最后挂载，避免拦截 /api）
if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )
    logger.info("已挂载前端目录: %s -> /", FRONTEND_DIR)
else:
    logger.warning("前端目录不存在: %s（仅暴露 API）", FRONTEND_DIR)