"""旅游行程请求模型。"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class InterestEnum(str, Enum):
    """兴趣维度枚举。"""
    HISTORY = "人文历史"
    FOOD = "美食体验"
    NATURE = "自然风光"
    CITY = "现代都市"
    LEISURE = "休闲度假"
    ART = "文艺体验"


class TripRequest(BaseModel):
    origin: str = Field(..., description="出发地")
    destination: str = Field(..., description="目的地")
    days: int = Field(3, ge=1, le=15, description="出行天数")
    interests: List[InterestEnum] = Field(
        default_factory=lambda: [InterestEnum.HISTORY, InterestEnum.FOOD],
        description="兴趣偏好",
    )
    travelers: int = Field(2, ge=1, le=20, description="出行人数")
    budget: Optional[str] = Field(None, description="预算（自由文本）")
    extra: Optional[str] = Field(None, description="其他要求")