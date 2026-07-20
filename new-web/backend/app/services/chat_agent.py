"""
聊天代理：function calling 循环 + SSE 流式输出。

事件类型:
- ("delta", str)              内容或 reasoning 片段
- ("tool_call", dict)         工具调用计划 {name, args}
- ("tool_result", dict)       工具执行结果 {name, result}
- ("error", str)              错误
- ("done", dict)              结束 {ok, turns}
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from ..config import load_config
from ..models.chat import ChatRequest
from .amap_client import AmapClient
from .llm_client import LLMClient
from .tool_registry import TOOLS, dispatch_tool

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
MAX_TURNS = 6


def _read_prompt(name: str) -> str:
    p = PROMPT_DIR / name
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def _serialize_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    """把 Pydantic / 自定义对象转成 OpenAI 兼容 dict。"""
    if hasattr(msg, "model_dump"):
        return msg.model_dump(exclude_none=True)
    if isinstance(msg, dict):
        return {k: v for k, v in msg.items() if v is not None}
    return dict(msg)


def _messages_with_system(req: ChatRequest) -> List[Dict[str, Any]]:
    sys_prompt = _read_prompt("chat_system.md") or "你是 AI 智行助手。"
    out: List[Dict[str, Any]] = [{"role": "system", "content": sys_prompt}]
    for m in req.messages:
        out.append(_serialize_message(m))
    return out


async def run_chat(req: ChatRequest) -> AsyncGenerator[Tuple[str, Any], None]:
    """聊天代理主循环。"""
    try:
        cfg = load_config()
        llm_cfg = cfg.get("llm") or {}
        amap_key = (cfg.get("amap") or {}).get("api_key", "")

        # 允许请求里临时覆盖
        base_url = req.base_url or llm_cfg.get("base_url", "")
        api_key = req.api_key or llm_cfg.get("api_key", "")
        model = req.model or llm_cfg.get("model", "MiniMax-M3")
        use_reasoning_split = bool(llm_cfg.get("use_reasoning_split", True))

        if not api_key:
            yield ("error", "LLM api_key 未配置")
            return

        llm = LLMClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            use_reasoning_split=use_reasoning_split,
        )

        amap: Optional[AmapClient] = None
        if amap_key:
            try:
                amap = AmapClient(amap_key)
            except Exception:
                amap = None

        messages = _messages_with_system(req)
        tools = TOOLS if req.tools_enabled else None

        turns = 0
        while turns < MAX_TURNS:
            turns += 1
            tool_calls_buffer: List[Dict[str, Any]] = []
            finish_reason: Optional[str] = None
            content_buf: str = ""

            # 1. 流式调用 LLM
            async for evt, payload in llm.stream_chat(messages, tools=tools):
                if evt == "reasoning":
                    yield ("delta", {"type": "reasoning", "text": payload})
                elif evt == "content":
                    content_buf += payload
                    yield ("delta", {"type": "content", "text": payload})
                elif evt == "tool_calls":
                    tool_calls_buffer = payload
                elif evt == "finish_reason":
                    finish_reason = payload
                elif evt == "error":
                    yield ("error", payload)
                    return

            # 2. 如果没有 tool_calls，结束
            if not tool_calls_buffer:
                yield ("done", {"ok": True, "turns": turns})
                return

            # 3. 把 assistant 的 tool_calls 写回 messages
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": content_buf or None,
                "tool_calls": [
                    {
                        "id": tc.get("id") or f"call_{turns}_{i}",
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for i, tc in enumerate(tool_calls_buffer)
                ],
            }
            messages.append(assistant_msg)

            # 4. 逐个 dispatch
            if amap is None:
                # 没配高德 key，所有工具都失败
                for tc in tool_calls_buffer:
                    name = tc["function"]["name"]
                    yield (
                        "tool_call",
                        {
                            "name": name,
                            "args": _safe_json_loads(tc["function"]["arguments"]),
                        },
                    )
                    yield (
                        "tool_result",
                        {"name": name, "result": {"ok": False, "error": "高德 api_key 未配置"}},
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.get("id") or f"call_{turns}",
                            "content": json.dumps(
                                {"ok": False, "error": "高德 api_key 未配置"}, ensure_ascii=False
                            ),
                        }
                    )
                continue

            for tc in tool_calls_buffer:
                name = tc["function"]["name"]
                raw_args = tc["function"]["arguments"] or ""
                args = _safe_json_loads(raw_args)

                yield ("tool_call", {"name": name, "args": args})

                result = await dispatch_tool(name, args, amap)
                yield ("tool_result", {"name": name, "result": result})

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id") or f"call_{turns}",
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )

        # 超过 MAX_TURNS
        yield ("done", {"ok": True, "turns": turns, "note": "已达最大工具调用轮数"})
    except Exception as e:  # noqa: BLE001
        logger.exception("run_chat 异常")
        yield ("error", f"对话失败: {e}")
    finally:
        # 清理 amap 客户端（如果打开了）
        try:
            if "amap" in locals() and amap and getattr(amap, "_client", None):
                await amap._client.aclose()
        except Exception:
            pass


def _safe_json_loads(s: str) -> Dict[str, Any]:
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        # 尝试容错：截到最后一个 '}'
        try:
            idx = s.rfind("}")
            if idx >= 0:
                return json.loads(s[: idx + 1])
        except Exception:
            pass
    return {"_raw": s}