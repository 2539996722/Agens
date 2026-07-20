# AI 智行助手 — 端云协同的智能出行助手

> "端云协同，AI + 高德地图为你打造便捷高效的智能出行体验"

一款手绘涂鸦风格（Hand-Drawn Sketch）的智能出行 Web 应用，结合 LLM 与高德开放平台，提供「旅游模式」和「日常聊天」两种 AI 出行能力。

## ✨ 功能一览

- 🧳 **旅游模式**：填表（出发地/目的地/天数/人数/兴趣偏好）→ AI 智能生成 Markdown 行程单
- 💬 **日常聊天模式**：自由对话，AI 可自动调用 12 个高德工具（天气、POI 搜索、路径规划等），工具调用结果以浅蓝便签卡片可视化
- ⚙️ **灵活配置**：LLM API Key / base_url / 模型名 / 高德 Key 全部可配置，配置保存在 `backend/data/config.json`
- 🧪 **一键测试**：配置页提供「测试 LLM 连接」和「测试高德连接」按钮
- 🎨 **手绘涂鸦 UI**：网格纸背景、粉彩便签卡片、不规则圆角、硬投影、弹性动画

## 📁 项目结构

```
AI旅游小助手/
├── backend/                # FastAPI 后端（端口 8765）
│   ├── app/
│   │   ├── main.py         # 入口
│   │   ├── config.py       # 配置持久化
│   │   ├── api/            # 路由层（settings / llm / amap）
│   │   ├── services/       # 业务层（LLM 客户端 / 高德客户端 / 旅游规划 / 聊天 Agent）
│   │   ├── models/         # Pydantic 数据模型
│   │   └── prompts/        # 系统提示词
│   ├── data/config.json    # 用户配置（自动生成）
│   ├── requirements.txt
│   └── run.bat             # Windows 一键启动
├── frontend/               # 纯静态前端（无构建步骤）
│   ├── index.html
│   ├── css/                # 6 个 CSS 文件
│   └── js/                 # 6 个 JS 文件
└── README.md
```

## 🚀 快速开始（Windows）

### 1. 安装依赖（首次）

```bat
cd E:\点头人工智能\AI旅游小助手\backend
C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe -m pip install -r requirements.txt
```

> 项目实际使用的 Python 路径为 `C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe`，是 Windows 上真正的 Python 3.11.9。
> 若你的 Python 路径不同，请相应修改 `run.bat`。

### 2. 启动后端

双击运行 `backend\run.bat`，会自动：

1. 设置 UTF-8 代码页
2. 启动 uvicorn 监听 `http://127.0.0.1:8765`
3. 用默认浏览器打开首页

或在命令行手动启动：

```bat
cd E:\点头人工智能\AI旅游小助手\backend
C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
```

### 3. 配置 LLM 与高德 Key

浏览器打开后会**自动弹出设置模态层**（因为尚未配置 Key）。在弹出框内填入：

| 字段 | 说明 |
|---|---|
| **LLM Base URL** | OpenAI 兼容接口地址，例如 `https://api.minimax.chat/v1` |
| **LLM API Key** | 你的 LLM 服务密钥 |
| **模型名** | 例如 `MiniMax-M3` |
| **启用 reasoning_split** | 勾选后会在生成旅游计划时把思考过程展示在折叠面板 |
| **高德 API Key** | 在 [高德开放平台](https://lbs.amap.com/dev/key/app) 申请 Web 服务类型 Key |

填好后点击：

1. 🧪 **测试 LLM 连接** → 看到绿色便签"成功"提示
2. 🧪 **测试高德连接** → 看到绿色便签"成功"提示
3. 💾 **保存配置** → 写入 `backend/data/config.json`

### 4. 开始使用

- **🧳 旅游模式**：填表 → 点击「✨ 生成计划」→ 流式看到 AI 输出 Markdown 行程
- **💬 日常聊天**：直接发消息，比如"明天上海天气怎么样？怎么从虹桥火车站到外滩？"→ AI 会自动调用高德工具查天气和路径

## 🔧 进阶使用

### LLM 兼容说明

后端使用 OpenAI Python SDK 调用 LLM，要求接口兼容 OpenAI Chat Completions 协议。模型如需启用思考模式（如 MiniMax-M3），需在请求体中带 `extra_body={"reasoning_split": True}`。后端已自动处理此参数；若你的模型不支持该字段（不会报错，只是没有 reasoning 输出）。

### 高德 Key 申请

1. 访问 [高德开放平台](https://lbs.amap.com/) 注册并完成开发者认证
2. 进入「应用管理 > 我的应用」创建一个「Web 服务」类型应用
3. 复制 API Key 填入前端配置页
4. 个人开发者的简单 Key 即可覆盖本项目所有 12 个工具
5. 若是企业签名 Key，可额外填 `security_jscode`（代码已预留支持，但需自行扩展签名逻辑）

### 后端 API 文档

启动后访问 `http://127.0.0.1:8765/docs` 查看 FastAPI 自动生成的 Swagger UI。

主要端点：

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET/POST` | `/api/settings` | 读写配置（GET 返回脱敏） |
| `POST` | `/api/settings/test/llm` | 测试 LLM 连接 |
| `POST` | `/api/settings/test/amap` | 测试高德连接 |
| `POST` | `/api/trip/plan/stream` | SSE 流式生成旅游计划 |
| `POST` | `/api/chat/stream` | SSE 流式日常聊天 |
| `GET` | `/api/amap/*` | 12 个高德工具的 HTTP 代理 |

## 🧠 技术架构

- **前端**：HTML + CSS + JS（**零依赖**，无构建步骤），手写 markdown 渲染器，SVG turbulence 滤镜模拟纸张纹理
- **后端**：FastAPI + Uvicorn + Pydantic v2 + httpx 异步
- **LLM 客户端**：OpenAI Python SDK（兼容 OpenAI Chat Completions 协议的所有服务）
- **地图能力**：后端直接调用高德 v3 REST API（用 `extra_body.reasoning_split` 提取思考过程）
- **Function Calling**：把 12 个高德工具注册为 OpenAI `tools` schema，聊天模式下由 LLM 自动调度

### Function Calling 流程

```
用户消息 → LLM (带 tools)
         ↓ 返回 tool_calls
后端 dispatch → 高德 REST API → tool result
         ↓ 回填 messages
LLM 再次调用 → 输出自然语言回复
         ↓ 循环直至无 tool_calls
SSE 流式推到前端 → 工具调用卡片可视化
```

## ❓ 常见问题

**Q: 启动后浏览器一直转圈？**
A: 检查 8765 端口是否被占用；或访问 `http://127.0.0.1:8765/api/health` 看后端是否正常。

**Q: 测试 LLM 失败？**
A: 检查 base_url 末尾是否带 `/v1`；检查 API Key 是否有效；后端日志窗口会显示详细错误。

**Q: 测试高德失败？**
A: 确认 Key 类型是「Web 服务」而非「Web 端 JS API」；个人 Key 默认带签名需求请看上面"高德 Key 申请"第 5 条。

**Q: 生成旅游计划时没有任何反应？**
A: 打开浏览器开发者工具 Network 面板，看 `/api/trip/plan/stream` 是否返回 200 + `text/event-stream`。

**Q: 终端日志中文乱码？**
A: 是 cp936 控制台编码问题，与服务本身无关。HTTP 响应全部是 UTF-8 正常中文。换用 Windows Terminal 或 VS Code 终端查看更舒服。

## 📜 License

仅供学习交流使用。