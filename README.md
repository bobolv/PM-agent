# PM Agent

PM Agent 是一个面向项目全生命周期的文档生成与管理软件骨架。系统以项目任务为入口，围绕需求调研、初步设计、详细设计、测试、部署、试运行、验收和运维等阶段，管理文档模板、上下文继承关系和 Markdown 交付物。

## 设计取舍

本项目采用前后端分离架构：

- 后端：Python 3.11 + FastAPI + SQLModel，负责项目、任务、阶段、模板、文档和大模型生成编排。
- 前端：独立 `frontend/` 静态应用，当前用于快速验证核心流程，后续可替换为 Vue/React。
- 数据库：结构化数据进入关系型数据库；生成的 Markdown 文档同时保存到数据库和文件存储目录。
- 大模型：默认使用 OpenAI 兼容接口，可通过 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_TEMPERATURE` 和 `OPENAI_API_KEY` 切换模型服务。
- Docker：提供 PostgreSQL、后端 API、前端 Nginx 三个服务，方便部署和演示。

这种设计的优点是边界清楚、易扩展、容易替换模型或前端；代价是早期文件、数据库、模型调用之间需要维护一致性，后续建议加入文档版本表、任务产物关联表和对象存储。

## 核心能力

- 新建项目时录入背景、需求任务、起止时间和任务拆分。
- 自动初始化标准生命周期阶段。
- 自动生成阶段文档模板和周报、月报等定期文档模板。
- 候选文档模板库可导出为 Markdown 文件，适合使用 Obsidian 管理。
- 支持自定义模板大纲，推荐使用 Markdown。
- 生成阶段文档时自动引入前序阶段产物。
- 生成定期文档时自动引入近期项目文档作为上下文。
- 未配置模型密钥时提供离线草稿，便于先验证流程。

## 项目结构

```text
.
├── src/pm_agent/
│   ├── api/          # FastAPI 路由和接口模型
│   ├── agent/        # Agent 抽象保留层
│   ├── config/       # 配置管理
│   ├── logging/      # 日志配置
│   ├── tools/        # 工具抽象保留层
│   ├── db.py         # 数据库连接
│   ├── lifecycle.py  # 生命周期和默认模板
│   ├── llm.py        # OpenAI 兼容模型客户端
│   ├── models.py     # 数据库模型
│   └── services.py   # 项目和文档生成服务
├── frontend/         # 前端静态应用
├── tests/
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## 本地运行

安装 `uv`：

```bash
pip install uv
```

安装依赖：

```bash
uv sync
```

复制环境变量：

```powershell
Copy-Item .env.example .env
```

启动后端：

```bash
uv run pm-agent-api
```

访问前端页面：

```text
http://127.0.0.1:8000
```

访问 API 文档：

```text
http://localhost:8000/docs
```

不要直接双击打开 `frontend/index.html`，否则样式、交互和 API 请求都不会正常加载。使用 Docker Compose 时会自动通过 Nginx 托管。

## Docker 运行

```bash
docker compose up --build
```

访问：

- 前端：http://localhost:8080
- 后端 API：http://localhost:8000/docs
- PostgreSQL：localhost:5432

## 模型配置

`.env` 中可以配置：

```text
APP_PORT=8000
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
LLM_TEMPERATURE=0.2
OPENAI_API_KEY=你的密钥
```

如果使用火山引擎方舟豆包模型，可以改为：

```text
LLM_PROVIDER=volcengine
LLM_TEMPERATURE=0.2
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
VOLCENGINE_MODEL=doubao-seed-2-1-pro-260628
VOLCENGINE_API_KEY=你的火山引擎方舟 API Key
```

`LLM_PROVIDER=volcengine` 时，系统会默认使用上面的火山方舟地址和豆包模型；如需临时覆盖，也可以继续通过 `LLM_BASE_URL` 和 `LLM_MODEL` 指定 OpenAI 兼容地址和模型名称。

修改 `.env` 后需要重启后端服务，新的模型地址和密钥才会生效。

如果本机 `8000` 端口被旧进程占用，可以在 `.env` 中改成 `APP_PORT=8001`，然后访问 `http://127.0.0.1:8001`。

## 候选模板库

系统启动后会把候选文档模板导出到：

```text
./template-library
```

每个模板是一个带 frontmatter 的 Markdown 文件，可以用 Obsidian 维护。修改后调用：

```bash
curl -X POST http://127.0.0.1:8000/api/document-catalog/sync-md
```

重新从 Markdown 同步到数据库。也可以手动导出：

```bash
curl -X POST "http://127.0.0.1:8000/api/document-catalog/export-md?overwrite=false"
```

## 后续演进建议

- 增加用户、角色、项目成员和审批流。
- 为文档增加版本管理、差异对比和发布状态。
- 增加任务产物表，让周报、月报按任务和时间窗口精确聚合。
- 引入向量检索或全文索引，把历史文档作为更可靠的上下文来源。
- 将 Markdown 文件存储迁移到 S3、MinIO 或企业文档库。
