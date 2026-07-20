"""
配置相关 API：
- GET  /api/settings
- POST /api/settings
- POST /api/settings/test/llm
- POST /api/settings/test/amap
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

from ..config import load_config, public_view, save_config
from ..models.settings import AmapTestRequest, FullConfig, LLMTestRequest
from ..services.amap_client import AmapClient, AmapError
from ..services.llm_client import LLMClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings():
    """返回脱敏后的配置。"""
    cfg = load_config()
    return {"ok": True, "config": public_view(cfg)}


@router.get("/raw")
async def get_settings_raw():
    """
    返回完整配置（含明文 key），**仅供本机前端使用**。
    本地访问即可，无需鉴权（已是本地应用）。
    """
    return {"ok": True, "config": load_config()}


@router.post("")
async def post_settings(payload: FullConfig):
    """保存完整配置（含明文 key）。"""
    try:
        cfg = payload.model_dump()
        save_config(cfg)
        return {"ok": True, "config": public_view(load_config())}
    except Exception as e:
        logger.exception("保存配置失败")
        raise HTTPException(status_code=500, detail={"ok": False, "error": str(e)})


@router.post("/test/llm")
async def test_llm(payload: LLMTestRequest):
    """测试 LLM 连接，返回首个 content 片段作为 sample_reply。"""
    if not payload.api_key:
        raise HTTPException(status_code=400, detail={"ok": False, "error": "缺少 api_key"})
    try:
        client = LLMClient(
            base_url=payload.base_url,
            api_key=payload.api_key,
            model=payload.model,
            use_reasoning_split=payload.use_reasoning_split,
            timeout=20.0,
        )
        start = time.time()
        sample_chunks: list[str] = []
        async for evt, val in client.stream_chat(
            messages=[
                {"role": "user", "content": payload.prompt or "你好"},
            ],
            temperature=0.7,
        ):
            if evt == "content":
                sample_chunks.append(val)
                if sum(len(s) for s in sample_chunks) >= 80:
                    break
        elapsed_ms = int((time.time() - start) * 1000)
        sample = "".join(sample_chunks).strip()[:200]
        return {"ok": True, "latency_ms": elapsed_ms, "sample_reply": sample}
    except Exception as e:
        logger.exception("LLM 测试失败")
        raise HTTPException(status_code=502, detail={"ok": False, "error": str(e)})


@router.post("/test/amap")
async def test_amap(payload: AmapTestRequest):
    """测试高德 key：调一次 weather。"""
    if not payload.api_key:
        raise HTTPException(status_code=400, detail={"ok": False, "error": "缺少 api_key"})
    try:
        async with AmapClient(payload.api_key) as client:
            data = await client.weather("北京")
        return {"ok": True, "sample": data}
    except AmapError as e:
        raise HTTPException(status_code=502, detail={"ok": False, "error": str(e), "info": e.info})
    except Exception as e:
        logger.exception("高德测试失败")
        raise HTTPException(status_code=502, detail={"ok": False, "error": str(e)})