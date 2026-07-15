# MemWeave（忆织）

[English](README.md)

> 把散落在文字、照片和声音里的碎片，整理成记忆。

MemWeave（忆织）是一个本地优先、以原始资料为依据的个人记忆整理项目。

你可以把文字、聊天记录、照片、录音、视频和访谈材料交给它。系统会先保存原始资料，再从有依据的内容中整理出人物的经历、说话方式、情绪反应、价值观、相处模式和声音特征，形成可以追溯来源的 A-M 结构化记忆库。

提取结果不会自动被当成事实。用户可以核对证据，处理不确定内容，选择保留、纠正、降低权重、隐藏或遗忘，再用经过约束的记忆生成聊天 Skill；声音输出也必须在明确授权后，朗读已经生成的固定文本。

这个项目不是为了“复活”、克隆或替代某个人，而是认真保存那些散落在资料里的细节。

## 主要功能

- 文字、文档、图片、音频、视频和访谈的 raw-first 摄取。
- 可追溯的 A-M 人格记忆库，覆盖事实、语言、情绪、价值观、关系、决策、边界和声音特征。
- 不确定内容的确认与处理：保留、纠正、降权、隐藏、遗忘。
- 可重新生成、可保存版本的运行时 Skill。
- 聊天时只检索相关记忆切片，不把完整人物库全部塞给模型。
- 兼容 OpenAI 协议的模型配置、模型发现和手动模型名回退。
- 可选 OCR、ASR、Supabase 登录入口、SQLite 文档存储、只读 MCP 工具和授权 IndexTTS2 声音输出。
- 主要工作台标签支持中英文切换，并提供响应式 Web 工作台和 Windows Electron 开发壳。

## 当前状态

MemWeave 目前是可运行的本地单用户 MVP 和源码仓库。资料摄取、证据审核、Skill 生成、聊天、存储、MCP、完整性检查和声音安全边界已经实现。

使用前需要了解这些边界：

- 外部 AI、OCR、ASR 和声音生成默认关闭或未配置。
- 后端没有生产级鉴权和多租户隔离，不应直接暴露到公网。
- 默认使用本地 JSON 存储，SQLite 文档存储是可选项。
- Electron 只是开发壳，不包含安装程序、自动更新或普通用户分发包。
- IndexTTS2 是可选的外部适配器；仓库不包含模型权重、参考音频或生成音频。

## 快速开始

环境要求：

- Windows 10 或 11，带 PowerShell
- Node.js 20 或更高版本
- Python 3.11 或更高版本

在仓库根目录运行：

```powershell
npm run setup
npm run dev
```

安装脚本会创建 `backend/.venv`，安装 Python/Node 依赖，并在本地 `.env` 不存在时从已脱敏的示例文件创建配置。

默认地址：

- Web：`http://127.0.0.1:3000`，端口占用时会尝试 3001-3003
- API 文档：`http://127.0.0.1:8000/docs`

需要模型能力时，再到“设置”页面配置兼容 OpenAI 协议的供应商。手动安装与常见问题见 [启动说明](docs/getting-started.md)。

## 桌面开发壳

完成依赖安装后运行：

```powershell
npm run client:check
npm run client:start
```

它会通过 Electron 启动本地前后端，但不会生成安装包。详情见 [桌面壳说明](docs/desktop-shell.zh-CN.md)。

## 验证

运行后端回归、质量策略、模型发现、桌面失败页和仓库卫生检查：

```powershell
npm test
```

运行前端检查：

```powershell
cd frontend
npm run typecheck
npm run lint
npm run build
```

## 核心数据关系

```text
raw_sources -> source_segments -> persona_items（A-M）
                          |               |
                          v               v
                  uncertain_items     generated Skills
                                             |
                                             v
                                      聊天检索切片
```

原始资料是证据记录，Persona 条目是结构化解释，Skill 是可以重新生成的运行时产物。聊天记录只是对话历史，可能产生待确认候选，但不会自动变成事实。

更多内容见 [架构说明](docs/architecture.zh-CN.md)。

## 目录结构

```text
backend/   FastAPI 接口、数据结构、存储、工作流和运行时安全门
frontend/  Next.js App Router 工作台
desktop/   Electron 开发壳
scripts/   安装、启动、依赖准备和仓库卫生脚本
tests/     可重复运行的回归与策略检查
docs/      架构、启动、桌面和声音边界文档
```

## 隐私与安全

不要提交 `.env`、API Key、人物档案、原始个人资料、数据库、日志、模型权重或音视频参考文件。仓库自带卫生检查，用于阻止最重要的发布残留。部署或处理敏感资料前请阅读 [SECURITY.md](SECURITY.md)。

## 参与贡献

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。涉及记忆、分类、聊天和声音的修改，应继续保留原始证据、来源归属、用户纠正入口和明确授权边界。

## 许可证

本项目使用 [PolyForm Noncommercial License 1.0.0](LICENSE)。

许可证允许个人、教育、研究和其他非商业用途；商业使用需要另行获得授权。该许可证属于非商业源码可用许可证，不是 OSI 认可的开源许可证。
