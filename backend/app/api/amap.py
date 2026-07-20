"""
高德 12 工具代理 API。

每个端点直接透传 query 参数到 amap_client，统一加 api_key。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from ..config import load_config
from ..services.amap_client import AmapClient, AmapError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/amap", tags=["amap"])


def _client() -> AmapClient:
    cfg = load_config()
    api_key = (cfg.get("amap") or {}).get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail={"ok": False, "error": "高德 api_key 未配置"})
    return AmapClient(api_key)


async def _safe(coro):
    try:
        return await coro
    except AmapError as e:
        raise HTTPException(
            status_code=502,
            detail={"ok": False, "error": str(e), "status": e.status, "info": e.info},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("amap 路由异常")
        raise HTTPException(status_code=500, detail={"ok": False, "error": str(e)})


@router.get("/geo")
async def geo(address: str = Query(...), city: Optional[str] = None):
    async with _client() as c:
        return await _safe(c.geo(address, city))


@router.get("/regeocode")
async def regeocode(location: str = Query(...)):
    async with _client() as c:
        return await _safe(c.regeocode(location))


@router.get("/ip_location")
async def ip_location(ip: Optional[str] = None):
    async with _client() as c:
        return await _safe(c.ip_location(ip))


@router.get("/weather")
async def weather(city: str = Query(...)):
    async with _client() as c:
        return await _safe(c.weather(city))


@router.get("/text_search")
async def text_search(
    keywords: str = Query(...),
    city: Optional[str] = None,
    types: Optional[str] = None,
):
    async with _client() as c:
        return await _safe(c.text_search(keywords, city, types))


@router.get("/around_search")
async def around_search(
    location: str = Query(...),
    keywords: Optional[str] = None,
    radius: Optional[str] = None,
):
    async with _client() as c:
        return await _safe(c.around_search(location, keywords, radius))


@router.get("/search_detail")
async def search_detail(poi_id: str = Query(..., alias="poi_id")):
    async with _client() as c:
        return await _safe(c.search_detail(poi_id))


@router.get("/direction/driving")
async def direction_driving(origin: str = Query(...), destination: str = Query(...)):
    async with _client() as c:
        return await _safe(c.direction_driving(origin, destination))


@router.get("/direction/walking")
async def direction_walking(origin: str = Query(...), destination: str = Query(...)):
    async with _client() as c:
        return await _safe(c.direction_walking(origin, destination))


@router.get("/direction/transit")
async def direction_transit(
    origin: str = Query(...),
    destination: str = Query(...),
    city: str = Query(...),
    cityd: str = Query(...),
):
    async with _client() as c:
        return await _safe(c.direction_transit(origin, destination, city, cityd))


@router.get("/direction/bicycling")
async def direction_bicycling(origin: str = Query(...), destination: str = Query(...)):
    async with _client() as c:
        return await _safe(c.direction_bicycling(origin, destination))


@router.get("/distance")
async def distance(
    origins: str = Query(...),
    destination: str = Query(...),
    type: str = Query("1"),
):
    async with _client() as c:
        return await _safe(c.distance(origins, destination, type))