"""
高德开放平台 v3 REST API 异步客户端。

与 Claude Code 进程内 MCP 工具一一对应:
- geo / regeocode / ip_location / weather
- text_search / around_search / search_detail
- direction_driving / direction_walking / direction_transit / direction_bicycling
- distance
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://restapi.amap.com"
DEFAULT_TIMEOUT = 10.0


class AmapError(RuntimeError):
    """高德 API 调用错误。"""

    def __init__(self, message: str, status: Optional[str] = None, info: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.info = info


class AmapClient:
    """高德 REST API 客户端。"""

    def __init__(self, api_key: str, timeout: float = DEFAULT_TIMEOUT):
        if not api_key:
            raise AmapError("高德 api_key 未配置")
        self.api_key = api_key
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "AmapClient":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._client is None:
            # 允许在未使用 with 的情况下调用
            self._client = httpx.AsyncClient(timeout=self._timeout)
            close_after = True
        else:
            close_after = False
        try:
            query = {"key": self.api_key, "output": "JSON", **params}
            url = f"{BASE_URL}{path}"
            logger.debug("请求高德: %s params=%s", path, {k: v for k, v in query.items() if k != "key"})
            resp = await self._client.get(url, params=query)
            data = resp.json()
        except httpx.HTTPError as e:
            raise AmapError(f"高德请求失败: {e}") from e
        except Exception as e:
            raise AmapError(f"高德响应解析失败: {e}") from e
        finally:
            if close_after and self._client is not None:
                await self._client.aclose()
                self._client = None

        # 高德 status: "1"=成功, "0"=失败
        status = str(data.get("status", "0"))
        if status != "1":
            info = data.get("info", "未知错误")
            raise AmapError(f"高德返回错误: {info}", status=status, info=info)
        return data

    # ---------- 地理编码 ----------

    async def geo(self, address: str, city: Optional[str] = None) -> Dict[str, Any]:
        """结构化地址 -> 经纬度坐标。"""
        params: Dict[str, Any] = {"address": address}
        if city:
            params["city"] = city
        return await self._get("/v3/geocode/geo", params)

    async def regeocode(self, location: str) -> Dict[str, Any]:
        """经纬度 -> 行政区划地址。location: 'lng,lat'"""
        return await self._get("/v3/geocode/regeo", {"location": location})

    async def ip_location(self, ip: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if ip:
            params["ip"] = ip
        return await self._get("/v3/ip", params)

    # ---------- 天气 ----------

    async def weather(self, city: str) -> Dict[str, Any]:
        """查询指定城市的实时天气。"""
        return await self._get("/v3/weather/weatherInfo", {"city": city, "extensions": "base"})

    # ---------- POI 搜索 ----------

    async def text_search(
        self,
        keywords: str,
        city: Optional[str] = None,
        types: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"keywords": keywords}
        if city:
            params["city"] = city
        if types:
            params["types"] = types
        return await self._get("/v3/place/text", params)

    async def around_search(
        self,
        location: str,
        keywords: Optional[str] = None,
        radius: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"location": location}
        if keywords:
            params["keywords"] = keywords
        if radius:
            params["radius"] = radius
        return await self._get("/v3/place/around", params)

    async def search_detail(self, poi_id: str) -> Dict[str, Any]:
        return await self._get("/v3/place/detail", {"id": poi_id})

    # ---------- 路径规划 ----------

    async def direction_driving(self, origin: str, destination: str) -> Dict[str, Any]:
        return await self._get(
            "/v3/direction/driving",
            {"origin": origin, "destination": destination},
        )

    async def direction_walking(self, origin: str, destination: str) -> Dict[str, Any]:
        return await self._get(
            "/v3/direction/walking",
            {"origin": origin, "destination": destination},
        )

    async def direction_transit(
        self,
        origin: str,
        destination: str,
        city: str,
        cityd: str,
    ) -> Dict[str, Any]:
        return await self._get(
            "/v3/direction/transit/integrated",
            {
                "origin": origin,
                "destination": destination,
                "city": city,
                "cityd": cityd,
            },
        )

    async def direction_bicycling(self, origin: str, destination: str) -> Dict[str, Any]:
        return await self._get(
            "/v3/direction/bicycling",
            {"origin": origin, "destination": destination},
        )

    # ---------- 距离 ----------

    async def distance(
        self,
        origins: str,
        destination: str,
        type: str = "1",
    ) -> Dict[str, Any]:
        """
        origins: 'lng,lat|lng,lat'
        type: 1=驾车, 0=直线, 3=步行
        """
        return await self._get(
            "/v3/distance",
            {"origins": origins, "destination": destination, "type": type},
        )


def extract_pois(text_search_result: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    """从 text_search 结果中提取精简 POI 列表。"""
    pois = text_search_result.get("pois") or []
    out: List[Dict[str, Any]] = []
    for p in pois[:limit]:
        loc = p.get("location") or ""
        # location 形如 "116.397026,39.918056"
        lng, lat = (loc.split(",") + ["", ""])[:2]
        out.append(
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "address": p.get("address") or p.get("adname") or "",
                "location": loc,
                "type": p.get("type"),
                "lng": lng,
                "lat": lat,
            }
        )
    return out