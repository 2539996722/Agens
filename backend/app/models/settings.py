"""配置相关 Pydantic 模型。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = "MiniMax-M3"
    use_reasoning_split: bool = True


class AmapConfig(BaseModel):
    api_key: str = ""
    security_jscode: str = ""
    sse_url: str = ""


class FullConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    amap: AmapConfig = Field(default_factory=AmapConfig)


class LLMTestRequest(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = "MiniMax-M3"
    use_reasoning_split: bool = True
    prompt: Optional[str] = "你好，请用一句话介绍你自己。"


class AmapTestRequest(BaseModel):
    api_key: str = ""