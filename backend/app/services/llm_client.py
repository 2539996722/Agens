"""
OpenAI 兼容 LLM 客户端封装。

特性:
- 每次调用可注入 base_url / api_key / model，方便测试连接
- 支持流式输出与 reasoning_split（reasoning_details 与 content 分离）
- 不可用时自动降级（reasoning 留空，正常处理 content）
"""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI 兼容异步客户端封装。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        use_reasoning_split: bool = True,
        timeout: float = 60.0,
    ):
        if not api_key:
            raise ValueError("LLM api_key 未配置")
        self.base_url = base_url or "https://api.openai.com/v1"
        self.api_key = api_key
        self.model = model or "MiniMax-M3"
        self.use_reasoning_split = bool(use_reasoning_split)
        self.timeout = timeout
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def with_overrides(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> "LLMClient":
        """返回一个新的 LLMClient，使用覆盖后的配置。"""
        return LLMClient(
            base_url=base_url or self.base_url,
            api_key=api_key or self.api_key,
            model=model or self.model,
            use_reasoning_split=self.use_reasoning_split,
            timeout=self.timeout,
        )

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Tuple[str, Any], None]:
        """
        流式调用 LLM。

        yield: (event_type, payload)
          - ("reasoning", str)
          - ("content", str)
          - ("tool_calls", list)
          - ("finish_reason", str)
          - ("error", str)
          - ("usage", dict) —— 偶尔
        """
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        body: Dict[str, Any] = {}
        if self.use_reasoning_split:
            body["reasoning_split"] = True
        if extra_body:
            body.update(extra_body)
        if body:
            kwargs["extra_body"] = body

        try:
            stream = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            logger.exception("LLM 流式调用失败")
            yield ("error", f"LLM 调用失败: {e}")
            return

        accumulated_tool_calls: List[Dict[str, Any]] = []
        finish_reason: Optional[str] = None

        async for chunk in stream:
            try:
                if not chunk.choices:
                    # 部分实现把 usage 放在无 choices 的 chunk 中
                    if getattr(chunk, "usage", None):
                        yield ("usage", chunk.usage.model_dump())
                    continue
                choice = chunk.choices[0]
                delta = choice.delta or {}

                # 1. reasoning（部分模型支持 reasoning_details[0].text）
                reasoning_text = _extract_reasoning(delta)
                if reasoning_text:
                    yield ("reasoning", reasoning_text)

                # 2. content
                content_piece = delta.content or ""
                if content_piece:
                    yield ("content", content_piece)

                # 3. tool_calls（流式累积）
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index if tc.index is not None else 0
                        # 扩展列表以容纳所有 index
                        while len(accumulated_tool_calls) <= idx:
                            accumulated_tool_calls.append(
                                {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            )
                        slot = accumulated_tool_calls[idx]
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.type:
                            slot["type"] = tc.type
                        fn = tc.function or {}
                        if getattr(fn, "name", None):
                            slot["function"]["name"] = (
                                slot["function"].get("name", "") + fn.name
                            )
                        if getattr(fn, "arguments", None):
                            slot["function"]["arguments"] = (
                                slot["function"].get("arguments", "") + fn.arguments
                            )

                # 4. finish_reason
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
            except Exception as e:
                logger.exception("解析 LLM chunk 失败: %s", e)
                yield ("error", f"解析流式响应失败: {e}")
                return

        if accumulated_tool_calls:
            yield ("tool_calls", accumulated_tool_calls)
        if finish_reason:
            yield ("finish_reason", finish_reason)

    async def non_stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """非流式调用，返回原始 message 字典（含 reasoning_details 等）。"""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools

        body: Dict[str, Any] = {}
        if self.use_reasoning_split:
            body["reasoning_split"] = True
        if body:
            kwargs["extra_body"] = body

        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            logger.exception("LLM 非流式调用失败")
            raise RuntimeError(f"LLM 调用失败: {e}") from e

        # 序列化为 dict
        try:
            return resp.model_dump()
        except Exception:
            # 兜底
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": getattr(resp.choices[0].message, "content", ""),
                        }
                    }
                ]
            }


def _extract_reasoning(delta: Any) -> str:
    """
    从 delta 中提取 reasoning 文本。

    支持多种可能的字段:
    - delta.reasoning_details[0].text
    - delta.reasoning
    - delta.reasoning_content
    """
    try:
        # 1. reasoning_details: list of {type, text, ...}
        rd = getattr(delta, "reasoning_details", None)
        if rd:
            # 取所有 text 片段
            parts = []
            for item in rd:
                text = getattr(item, "text", None)
                if text:
                    parts.append(text)
            if parts:
                return "".join(parts)

        # 2. reasoning / reasoning_content 字段
        rc = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if rc:
            return rc if isinstance(rc, str) else str(rc)
    except Exception:
        pass
    return ""