"""
12 个高德工具的 OpenAI tools schema + 调度器。

- TOOLS: 可直接传给 OpenAI chat.completions 的 tools 参数
- dispatch_tool(name, args, amap_client): 根据 name 调用 amap_client 对应方法
"""
from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Tuple

from .amap_client import AmapClient, AmapError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OpenAI tools schema 定义
# ---------------------------------------------------------------------------

TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "amap_geo",
            "description": "将结构化地址转换为经纬度坐标。例如：'北京市朝阳区阜通东大街' -> '116.483038,39.990633'",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "结构化地址描述"},
                    "city": {"type": "string", "description": "城市（可选，用于限定范围）"},
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_regeocode",
            "description": "将经纬度坐标（'lng,lat'）转换为行政区划地址。",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "经纬度坐标，格式 'lng,lat'"},
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_ip_location",
            "description": "根据 IP 地址定位所在城市（不传 ip 则定位当前请求 IP）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IP 地址（可选）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_weather",
            "description": "查询指定城市的实时天气（实况）。城市名或 adcode 均可，例如 '北京' 或 '110000'。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名或 adcode"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_text_search",
            "description": "关键词搜索 POI，返回景点、餐厅、商户等列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {"type": "string", "description": "搜索关键词，如 '西湖' / '火锅'"},
                    "city": {"type": "string", "description": "城市（可选）"},
                    "types": {"type": "string", "description": "POI 分类（可选，如 '050000' 表示餐饮）"},
                },
                "required": ["keywords"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_around_search",
            "description": "在指定经纬度周边搜索 POI。",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "中心点 'lng,lat'"},
                    "keywords": {"type": "string", "description": "搜索关键词（可选）"},
                    "radius": {"type": "string", "description": "搜索半径（米），默认 1000"},
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_search_detail",
            "description": "通过 POI ID 查询详细信息（地址、电话、评分等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "poi_id": {"type": "string", "description": "POI 唯一 ID"},
                },
                "required": ["poi_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_direction_driving",
            "description": "驾车路径规划，返回距离、耗时、路线步骤。",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "起点 'lng,lat'"},
                    "destination": {"type": "string", "description": "终点 'lng,lat'"},
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_direction_walking",
            "description": "步行路径规划，最大 100km。",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "起点 'lng,lat'"},
                    "destination": {"type": "string", "description": "终点 'lng,lat'"},
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_direction_transit",
            "description": "公交 / 地铁 / 火车 综合路径规划，跨城场景需指定 city 与 cityd。",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "起点 'lng,lat'"},
                    "destination": {"type": "string", "description": "终点 'lng,lat'"},
                    "city": {"type": "string", "description": "起点城市"},
                    "cityd": {"type": "string", "description": "终点城市"},
                },
                "required": ["origin", "destination", "city", "cityd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_direction_bicycling",
            "description": "骑行路径规划，最大 500km。",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "起点 'lng,lat'"},
                    "destination": {"type": "string", "description": "终点 'lng,lat'"},
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "amap_distance",
            "description": "测量两点或多点之间的距离。type: 1=驾车, 0=直线, 3=步行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "origins": {
                        "type": "string",
                        "description": "起点 'lng,lat'，多个用 '|' 分隔",
                    },
                    "destination": {"type": "string", "description": "终点 'lng,lat'"},
                    "type": {"type": "string", "description": "1=驾车, 0=直线, 3=步行，默认 1"},
                },
                "required": ["origins", "destination"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# 调度：name -> amap_client 方法
# ---------------------------------------------------------------------------

ToolHandler = Callable[..., Awaitable[Dict[str, Any]]]

# 工具名 -> (方法, 期望参数顺序)
_DISPATCH_TABLE: Dict[str, Tuple[str, List[str]]] = {
    "amap_geo": ("geo", ["address", "city"]),
    "amap_regeocode": ("regeocode", ["location"]),
    "amap_ip_location": ("ip_location", ["ip"]),
    "amap_weather": ("weather", ["city"]),
    "amap_text_search": ("text_search", ["keywords", "city", "types"]),
    "amap_around_search": ("around_search", ["location", "keywords", "radius"]),
    "amap_search_detail": ("search_detail", ["poi_id"]),
    "amap_direction_driving": ("direction_driving", ["origin", "destination"]),
    "amap_direction_walking": ("direction_walking", ["origin", "destination"]),
    "amap_direction_transit": ("direction_transit", ["origin", "destination", "city", "cityd"]),
    "amap_direction_bicycling": ("direction_bicycling", ["origin", "destination"]),
    "amap_distance": ("distance", ["origins", "destination", "type"]),
}


def _stringify(value: Any) -> str:
    """LLM 返回的数字 / 列表 / 字典统一转字符串再传给高德。"""
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "|".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


async def dispatch_tool(
    name: str,
    args: Dict[str, Any],
    amap_client: AmapClient,
) -> Dict[str, Any]:
    """
    根据 name 调用 amap_client 对应方法。

    返回 {"ok": True, "data": {...}} 或 {"ok": False, "error": "..."}
    """
    if name not in _DISPATCH_TABLE:
        return {"ok": False, "error": f"未知工具: {name}"}

    method_name, param_order = _DISPATCH_TABLE[name]
    method = getattr(amap_client, method_name, None)
    if method is None:
        return {"ok": False, "error": f"高德客户端缺少方法: {method_name}"}

    kwargs: List[Any] = []
    for p in param_order:
        val = args.get(p)
        kwargs.append(_stringify(val))

    try:
        data = await method(*kwargs)
        return {"ok": True, "data": data}
    except AmapError as e:
        logger.warning("工具 %s 调用失败: %s", name, e)
        return {"ok": False, "error": str(e), "status": e.status, "info": e.info}
    except Exception as e:  # noqa: BLE001
        logger.exception("工具 %s 异常", name)
        return {"ok": False, "error": f"工具异常: {e}"}


def tool_names() -> List[str]:
    """返回所有工具名（用于调试）。"""
    return list(_DISPATCH_TABLE.keys())