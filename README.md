<div align="center">

# ⚡ PromptForge

**开源提示词工程工作台 — 管理版本化、测试并交付你的 AI 提示词**

*Open-source prompt engineering workbench — manage, version, test and ship prompts.*

[![CI](https://github.com/wangzi5151/promptforge/actions/workflows/ci.yml/badge.svg)](https://github.com/wangzi5151/promptforge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-6c8cff.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3ddc97.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-⚡-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](Dockerfile)

本地优先 · 零外部依赖 · 团队就绪 · 永久免费开源核心

</div>

---

## 🎯 为什么是 PromptForge？

AI Agent 与提示词工程是当下开源最火热的赛道。然而多数团队把提示词散落在聊天记录、备忘录和代码注释里——**提示词是资产，值得被工程化管理**。

PromptForge 把你的提示词变成**可版本化、可测试、可交付**的一等公民：

| 能力 | 说明 |
|---|---|
| 🗂️ **提示词库** | 搜索、分类、标签、收藏，统一管理所有提示词 |
| 🕘 **版本历史** | 每次修改自动留档，一键回滚任意历史版本 |
| 🔤 **变量模板** | `{{变量}}` 占位符自动识别，实时渲染预览 |
| ▶ **测试运行器** | 填变量 → 实时渲染 → 直接投喂 LLM，运行记录留存 |
| 📊 **数据分析** | 14 天运行趋势、Top 提示词、分类分布 |
| 🔑 **API 密钥** | 为团队与自动化流程签发 REST API 密钥 |
| 📦 **一键导出** | 全量 JSON 导出，数据主权在你手里 |
| 🌐 **内置 SPA** | 精美玻璃拟态暗色界面，流畅动效 |

## 🚀 快速开始

```bash
git clone https://github.com/wangzi5151/promptforge.git
cd promptforge
pip install -r requirements-dev.txt
make run
# 打开 http://localhost:8000
```

首次启动自动初始化 SQLite 数据库并注入 8 条精选演示提示词。

### Docker 部署（推荐生产）

```bash
docker compose up -d --build
# 打开 http://localhost:8000
```

数据持久化在 `promptforge-data` 卷中。

## 📡 REST API

启动后访问 **`/docs`** 获取完整交互式 Swagger 文档。核心端点：

```http
GET    /api/prompts                 # 列表（支持 ?q=&category=&tag=&favorites=）
POST   /api/prompts                 # 创建
PATCH  /api/prompts/{id}            # 更新（正文变更自动产生新版本）
DELETE /api/prompts/{id}            # 删除
GET    /api/prompts/{id}/versions   # 版本历史
POST   /api/prompts/{id}/run        # 变量渲染运行
GET    /api/analytics               # 分析指标
GET    /api/export                  # 全量导出
```

示例：

```bash
curl -X POST http://localhost:8000/api/prompts \
  -H "Content-Type: application/json" \
  -d '{"title":"翻译助手","body":"将以下{{lang}}文本翻译成中文：{{text}}"}'
```

## 💰 商业模式（Open Core）

| | Community（本仓库） | Pro ¥49/月 | Enterprise 定制 |
|---|---|---|---|
| 提示词管理 / 版本 / 运行器 | ✅ | ✅ | ✅ |
| 多工作区与团队协作 | — | ✅ | ✅ |
| A/B 测试与评分看板 | — | ✅ | ✅ |
| 云同步 / SSO / 审计日志 | — | — | ✅ |
| 协议 | MIT 开源 | 订阅 | 商业授权 |

开源核心永久免费；界面内置定价页，可按需替换为你自己的支付渠道。

## 🏗️ 架构

```
├── app/
│   ├── main.py          # FastAPI 应用 + REST API
│   ├── db.py            # SQLite 数据层（WAL，线程安全）
│   ├── config.py        # 环境变量配置
│   └── static/index.html # 内置 SPA（零构建，无前端依赖）
├── tests/test_api.py    # Pytest 全覆盖测试
├── Dockerfile / docker-compose.yml
└── .github/workflows/ci.yml  # CI：Python 3.10–3.12 + Docker 构建
```

技术选型：**FastAPI + SQLite + 原生 SPA**——单进程、零数据库服务、单二进制式部署，是自托管工具的最优解。

## 🛣️ 路线图

- [ ] 提示词评分与 A/B 对比
- [ ] 团队协作与权限
- [ ] MCP Server 接入（作为提示词工具源）
- [ ] 多语言 i18n
- [ ] 模型调用成本分析

## 🤝 贡献

欢迎 PR！见 [CONTRIBUTING.md](CONTRIBUTING.md)。测试全绿即可合并。

## 📄 许可

[MIT](LICENSE) © 2026 PromptForge contributors
