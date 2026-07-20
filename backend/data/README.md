# `backend/data/`

本目录用于存放用户配置和运行期数据。

## 文件

| 文件 | 是否入库 | 说明 |
|---|---|---|
| `config.json` | ❌ 不入库 | 用户实际配置（含 LLM / 高德 API Key），被 `.gitignore` 排除 |
| `config.example.json` | ✅ 入库 | 配置模板，首次运行会复制为 `config.json` |

## 首次运行

后端启动时会自动：

1. 若 `config.json` 不存在 → 从 `config.example.json` 拷贝一份
2. 若拷贝源也不存在 → 写入内置的默认配置（key 为空）

用户在浏览器打开页面后，**第一次会自动弹出设置页**，填写 LLM 与高德 Key 即可。

## 迁移配置

把 `config.json` 拷到另一台机器的同目录即可，无需重新配置。
