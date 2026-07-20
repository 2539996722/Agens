"""
LLM 流式 API（SSE）：
- POST /api/trip/plan/stream
- POST /api/chat/stream
"""
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..models.chat import ChatRequest
from ..models.trip import TripRequest
from ..services.chat_agent import run_chat
from ..services.trip_planner import run_trip_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["llm"])


def _sse_format(event: str, data: Any) -> bytes:
    """
    构造单条 SSE 数据：event: <name>\ndata: <单行 JSON>\n\n
    """
    try:
        payload = json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        payload = json.dumps({"raw": str(data)}, ensure_ascii=False)
    # data 必须单行
    payload = payload.replace("\r\n", " ").replace("\n", " ")
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


async def _trip_stream(req: TripRequest) -> AsyncGenerator[bytes, None]:
    try:
        async for evt, payload in run_trip_plan(req):
            if evt == "reasoning":
                yield _sse_format("reasoning", {"text": payload})
            elif evt == "content":
                yield _sse_format("content", {"text": payload})
            elif evt == "refs":
                yield _sse_format("refs", payload)
            elif evt == "error":
                yield _sse_format("error", {"message": payload})
                yield _sse_format("done", {"ok": False})
                return
            elif evt == "done":
                yield _sse_format("done", payload)
                return
            else:
                yield _sse_format(evt, payload)
    except Exception as e:
        logger.exception("trip stream 异常")
        yield _sse_format("error", {"message": f"服务器异常: {e}"})
        yield _sse_format("done", {"ok": False})


async def _chat_stream(req: ChatRequest) -> AsyncGenerator[bytes, None]:
    try:
        async for evt, payload in run_chat(req):
            if evt == "delta":
                yield _sse_format("delta", payload)
            elif evt == "tool_call":
                yield _sse_format("tool_call", payload)
            elif evt == "tool_result":
                yield _sse_format("tool_result", payload)
            elif evt == "error":
                yield _sse_format("error", {"message": payload})
                yield _sse_format("done", {"ok": False})
                return
            elif evt == "done":
                yield _sse_format("done", payload)
                return
            else:
                yield _sse_format(evt, payload)
    except Exception as e:
        logger.exception("chat stream 异常")
        yield _sse_format("error", {"message": f"服务器异常: {e}"})
        yield _sse_format("done", {"ok": False})


@router.post("/trip/plan/stream")
async def trip_plan_stream(req: TripRequest):
    return StreamingResponse(
        _trip_stream(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    return StreamingResponse(
        _chat_stream(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )