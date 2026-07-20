"""
旅游行程规划服务。

流程:
1. 预处理：asyncio.gather 并发调用高德
   - 出发地 / 目的地 geocode
   - 出发地 / 目的地天气（容错）
   - 两地距离（容错）
   - 每个兴趣维度的关键词搜索（容错）
2. 把预处理结果拼成 JSON 注入 user prompt
3. 调 LLM 流式生成 Markdown 行程
4. SSE 事件:
   - event: refs       候选 POI 列表
   - event: reasoning  推理片段
   - event: content    内容片段
   - event: error      错误
   - event: done       结束
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Tuple

from ..config import load_config
from ..models.trip import InterestEnum, TripRequest
from .amap_client import AmapClient, extract_pois
from .llm_client import LLMClient

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


# 兴趣 -> 搜索关键词 & POI 类型映射
INTEREST_KEYWORDS: Dict[InterestEnum, List[str]] = {
    InterestEnum.HISTORY: ["历史古迹", "博物馆", "古城墙"],
    InterestEnum.FOOD: ["特色美食", "本地小吃", "老字号餐厅"],
    InterestEnum.NATURE: ["自然风光", "森林公园", "山水景区"],
    InterestEnum.CITY: ["地标建筑", "CBD", "城市观光"],
    InterestEnum.LEISURE: ["度假村", "温泉", "海滨浴场"],
    InterestEnum.ART: ["艺术展馆", "文创园", "独立书店"],
}


def _read_prompt(name: str) -> str:
    p = PROMPT_DIR / name
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def _safe_location_str(geo_res: Dict[str, Any]) -> str:
    """从 geo 结果提取 'lng,lat' 字符串，失败返回 ''。"""
    try:
        geocodes = geo_res.get("geocodes") or []
        if geocodes:
            return geocodes[0].get("location", "") or ""
    except Exception:
        pass
    return ""


def _safe_weather_text(weather_res: Dict[str, Any]) -> str:
    """把 weather 结果转成一句简短文字。"""
    try:
        lives = weather_res.get("lives") or []
        if lives:
            w = lives[0]
            return (
                f"{w.get('province','')}{w.get('city','')} "
                f"天气 {w.get('weather','未知')}，"
                f"{w.get('temperature','?')}℃，"
                f"{w.get('winddirection','?')}风 "
                f"{w.get('windpower','?')}级，"
                f"湿度 {w.get('humidity','?')}%"
            )
    except Exception:
        pass
    return "天气数据暂未获取到"


def _safe_distance_text(dist_res: Dict[str, Any]) -> str:
    try:
        results = dist_res.get("results") or []
        if results:
            r = results[0]
            return f"直线距离 {r.get('distance','?')} 米，驾车 {r.get('duration','?')} 秒"
    except Exception:
        pass
    return "距离数据暂未获取到"


async def _gather_prefetch(req: TripRequest, amap: AmapClient) -> Dict[str, Any]:
    """
    并发预处理：高德查询。
    任一任务失败不影响其他，单独 try/except 容错。

    设计要点：不使用 asyncio.create_task，因为当内部协程抛异常时，
    Task 会进入"异常状态"，再调用 t.result()/t.exception() 在某些场景下
    会触发 InvalidStateError。我们改为直接定义 async 函数 safe()，
    在调用处用 try/except 包住 await，逻辑更直白可靠。
    """
    out: Dict[str, Any] = {
        "origin": {"geo": None, "weather": None, "error": None},
        "destination": {"geo": None, "weather": None, "error": None},
        "distance": None,
        "pois_by_interest": {},
        "all_pois": [],
    }

    # 用普通函数 + 显式 try 代替 Task
    async def call(label: str, sink: Dict[str, Any], coro_factory):
        try:
            return await coro_factory()
        except Exception as e:  # noqa: BLE001
            logger.warning("预处理子任务 %s 失败: %s", label, e)
            if sink is not None:
                sink["error"] = str(e)
            return None

    # ---- 第一阶段：geo 必须先完成，拿到经纬度后才能算距离 ----
    origin_geo_res, dest_geo_res = await asyncio.gather(
        call("origin_geo", out["origin"], lambda: amap.geo(req.origin)),
        call("dest_geo", out["destination"], lambda: amap.geo(req.destination)),
    )
    out["origin"]["geo"] = origin_geo_res
    out["destination"]["geo"] = dest_geo_res

    origin_loc = _safe_location_str(origin_geo_res) if origin_geo_res else ""
    dest_loc = _safe_location_str(dest_geo_res) if dest_geo_res else ""

    # ---- 第二阶段：并发 weather + distance + 兴趣 POI ----
    interest_calls = []
    for interest in req.interests:
        kws = INTEREST_KEYWORDS.get(interest, [])
        for kw in kws:
            interest_calls.append((interest, kw, call(
                f"poi/{interest.value}/{kw}", None,
                lambda k=kw: amap.text_search(keywords=k, city=req.destination),
            )))

    second_phase = [
        call("origin_weather", out["origin"], lambda: amap.weather(req.origin)),
        call("dest_weather", out["destination"], lambda: amap.weather(req.destination)),
    ]
    if origin_loc and dest_loc:
        second_phase.append(call("distance", None, lambda: amap.distance(origin_loc, dest_loc, type="1")))

    second_results = await asyncio.gather(*second_phase, return_exceptions=False)

    out["origin"]["weather"] = second_results[0]
    out["destination"]["weather"] = second_results[1]
    out["distance"] = second_results[2] if len(second_results) > 2 else None

    # ---- 第三阶段：兴趣 POI ----
    interest_results = await asyncio.gather(*[c[2] for c in interest_calls], return_exceptions=False)

    all_pois: List[Dict[str, Any]] = []
    pois_by_interest: Dict[str, List[Dict[str, Any]]] = {i.value: [] for i in req.interests}
    for (interest, kw, _), res in zip(interest_calls, interest_results):
        if not res:
            continue
        try:
            items = extract_pois(res, limit=3)
        except Exception:
            continue
        pois_by_interest[interest.value].extend(items)

    # 去重 by id
    for interest_value, items in pois_by_interest.items():
        seen = set()
        uniq: List[Dict[str, Any]] = []
        for it in items:
            pid = it.get("id")
            if pid and pid in seen:
                continue
            if pid:
                seen.add(pid)
            uniq.append(it)
        pois_by_interest[interest_value] = uniq[:5]
        all_pois.extend(uniq[:5])

    out["pois_by_interest"] = pois_by_interest
    out["all_pois"] = all_pois
    return out


def _build_user_prompt(req: TripRequest, prefetch: Dict[str, Any]) -> str:
    """把预处理结果注入 user prompt。"""
    lines: List[str] = []
    lines.append(f"出发地：{req.origin}")
    lines.append(f"目的地：{req.destination}")
    lines.append(f"出行天数：{req.days} 天")
    lines.append(f"兴趣偏好：{', '.join(i.value for i in req.interests)}")
    lines.append(f"出行人数：{req.travelers} 人")
    if req.budget:
        lines.append(f"预算：{req.budget}")
    if req.extra:
        lines.append(f"其他要求：{req.extra}")
    lines.append("")

    lines.append("【已知信息】(请基于这些事实生成行程，地点必须出自此清单)")
    lines.append(
        json.dumps(
            {
                "origin": {
                    "location": _safe_location_str(prefetch["origin"]["geo"] or {}),
                    "weather": _safe_weather_text(prefetch["origin"]["weather"] or {}),
                },
                "destination": {
                    "location": _safe_location_str(prefetch["destination"]["geo"] or {}),
                    "weather": _safe_weather_text(prefetch["destination"]["weather"] or {}),
                },
                "distance": _safe_distance_text(prefetch["distance"] or {}),
                "candidate_pois": prefetch.get("pois_by_interest", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    lines.append("")
    lines.append("请按 system 中的格式输出 Markdown 行程。")
    return "\n".join(lines)


async def run_trip_plan(req: TripRequest) -> AsyncGenerator[Tuple[str, Any], None]:
    """
    异步生成器：产出 SSE 事件元组 (event_type, payload)。

    event_type ∈ {"refs", "reasoning", "content", "error", "done"}
    """
    try:
        cfg = load_config()
        amap_key = (cfg.get("amap") or {}).get("api_key", "")
        llm_cfg = cfg.get("llm") or {}
        if not amap_key:
            yield ("error", "高德 api_key 未配置，请先在「配置」页填写")
            return
        if not llm_cfg.get("api_key"):
            yield ("error", "LLM api_key 未配置，请先在「配置」页填写")
            return

        async with AmapClient(amap_key) as amap:
            prefetch = await _gather_prefetch(req, amap)

        # 把候选 POI 推给前端
        yield ("refs", {"pois": prefetch.get("all_pois", [])})

        # 构造 LLM 消息
        system_prompt = _read_prompt("trip_system.md")
        if not system_prompt:
            system_prompt = "你是 AI 旅游规划师。"
        user_prompt = _build_user_prompt(req, prefetch)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        llm = LLMClient(
            base_url=llm_cfg.get("base_url", ""),
            api_key=llm_cfg.get("api_key", ""),
            model=llm_cfg.get("model", "MiniMax-M3"),
            use_reasoning_split=bool(llm_cfg.get("use_reasoning_split", True)),
        )

        async for evt, payload in llm.stream_chat(messages):
            if evt == "error":
                yield ("error", payload)
                return
            # reasoning / content 透传
            yield (evt, payload)

        yield ("done", {"ok": True})
    except Exception as e:  # noqa: BLE001
        logger.exception("run_trip_plan 异常")
        yield ("error", f"行程生成失败: {e}")