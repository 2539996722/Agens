"""
配置加载与保存工具。

负责:
- 定位 data/config.json (Windows 中文路径安全)
- 读取 / 写入 (原子写)
- 提供默认值与脱敏辅助
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict

# backend/app/config.py  ->  backend/data/
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
CONFIG_PATH: Path = DATA_DIR / "config.json"
EXAMPLE_PATH: Path = DATA_DIR / "config.example.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "llm": {
        "base_url": "",
        "api_key": "",
        "model": "MiniMax-M3",
        "use_reasoning_split": True,
    },
    "amap": {
        "api_key": "",
        "security_jscode": "",
        "sse_url": "",
    },
}


def ensure_config_file() -> None:
    """确保 data/config.json 存在；不存在则从模板拷贝。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        return
    if EXAMPLE_PATH.exists():
        shutil.copyfile(EXAMPLE_PATH, CONFIG_PATH)
    else:
        # 没有模板则写入默认配置
        save_config(DEFAULT_CONFIG)


def load_config() -> Dict[str, Any]:
    """加载配置；若文件不存在或损坏则返回默认配置。"""
    ensure_config_file()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return json.loads(json.dumps(DEFAULT_CONFIG))  # 深拷贝

    # 合并默认值，避免缺字段
    merged: Dict[str, Any] = json.loads(json.dumps(DEFAULT_CONFIG))
    for k, v in (data or {}).items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged


def save_config(cfg: Dict[str, Any]) -> None:
    """原子写入配置（先写 .tmp 再 rename）。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # 深合并默认值，避免保存时丢字段
    merged: Dict[str, Any] = json.loads(json.dumps(DEFAULT_CONFIG))
    for k, v in (cfg or {}).items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v

    fd, tmp_path = tempfile.mkstemp(prefix="config_", suffix=".tmp", dir=str(DATA_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONFIG_PATH)
    except Exception:
        # 清理临时文件
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def mask_key(key: str) -> str:
    """脱敏显示 key：前 4 + 后 2，中间 ***。"""
    if not key:
        return ""
    if len(key) <= 6:
        return "*" * len(key)
    return f"{key[:4]}***{key[-2:]}"


def public_view(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """返回给前端展示的脱敏视图。"""
    llm = cfg.get("llm", {}) or {}
    amap = cfg.get("amap", {}) or {}
    return {
        "llm": {
            "base_url": llm.get("base_url", ""),
            "api_key_masked": mask_key(llm.get("api_key", "")),
            "model": llm.get("model", ""),
            "use_reasoning_split": bool(llm.get("use_reasoning_split", True)),
        },
        "amap": {
            "api_key_masked": mask_key(amap.get("api_key", "")),
            "security_jscode": amap.get("security_jscode", ""),
            "sse_url": amap.get("sse_url", ""),
        },
    }