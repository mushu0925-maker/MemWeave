# MemWeave（忆织）

[English](README.md)

> 把散落在文字、照片和声音里的碎片，整理成记忆。

我做 MemWeave，是因为一个人的记忆很少会整齐地留在同一个地方。它们通常散在聊天记录、文档、照片、录音、视频和访谈里。

这个项目先保存这些原始资料，再从中整理出能够追溯来源的细节。模型提取的结果不会直接变成“事实”：用户可以查看证据、纠正误解，也可以对敏感或不确定内容选择降权、隐藏和遗忘。

经过确认的内容可以被组装成聊天时使用的 Skill。在另行取得明确授权后，还可以用外部声音模型朗读已经生成的固定回复。

MemWeave 不是“复活”工具，也不会把模型生成的回复说成某个人真实说过的话。

## 资料如何变成可用记忆

1. 先保存原文或上传文件，不让分类失败把证据丢掉。
2. 把需要处理的内容拆成片段，记录它属于谁、来自哪里。
3. 将有证据的细节整理到 A-M 个人库，包括事实、语言、情绪、价值观、关系、决策、边界和说话特征。
4. 把不清楚、有冲突或较敏感的解释放进待确认区，而不是默默采纳。
5. 根据当前记忆生成可重建的 Skill，聊天时只取当前问题需要的部分。

待确认内容支持保留、纠正、降权、隐藏和遗忘。纠正后的内容会重新走证据流程；隐藏或遗忘的内容不会进入聊天和 Skill。

## 已完成的功能

- 文字、文档、图片、音频、视频和访谈答案的资料摄取。
- 关联证据的 A-M 个人库，并保留置信度、稳定性、适用范围和风险信息。
- 不确定内容审核、定向追问以及保留/纠正/降权/隐藏/遗忘处理。
- 可重新生成的 Skill 预览、版本保存和按消息检索的聊天上下文。
- 兼容 OpenAI 协议的供应商配置、模型发现和手动模型名输入。
- 可选 OCR、ASR、SQLite 文档存储、只读 MCP 工具、Supabase 登录入口和授权 IndexTTS2 输出。
- 响应式 Next.js 工作台、主要标签中英文切换，以及 Windows Electron 开发壳。
- 后端回归、策略、桌面、仓库卫生和 CI 检查。

## 现在的边界

MemWeave 目前是本地单用户 MVP。核心流程可以运行，适合开发和项目展示，但它还不是可直接上线的公网服务，也不是已打包的桌面产品。

- 外部 AI、OCR、ASR 和声音生成默认关闭或未配置。
- FastAPI 后端没有生产级鉴权和多租户隔离，不能直接暴露到公网。
- 默认使用本地 JSON。可选 SQLite 保存的仍是同类文档数据，不是多用户关系型设计。
- Electron 只是开发壳，没有安装程序、代码签名、自动更新或内置运行环境。
- IndexTTS2 是可选外部适配器。仓库不包含模型权重、声音参考和生成音频。

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

安装脚本会创建 `backend/.venv`，安装 Python 和 Node 依赖，并且只在本地 `.env` 不存在时复制已脱敏的示例配置。

默认地址：

- Web：`http://127.0.0.1:3000`，端口占用时尝试 3001-3003
- API 文档：`http://127.0.0.1:8000/docs`

只有在需要模型能力时，才需要在“设置”中配置兼容 OpenAI 协议的供应商。手动安装和常见问题见 [启动说明](docs/getting-started.md)。

IndexTTS2 使用单独的本地适配器，启用前请先阅读 [授权声音输出](docs/authorized-voice.zh-CN.md)。

## 桌面开发壳

完成依赖安装后运行：

```powershell
npm run client:check
npm run client:start
```

这两条命令会在 Electron 中启动本地前后端，不会生成安装包。详情见 [桌面壳说明](docs/desktop-shell.zh-CN.md)。

## 验证

运行后端回归、策略、模型发现、桌面和仓库卫生检查：

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

## 数据主线

```text
raw_sources -> source_segments -> persona_items（A-M）
                          |               |
                          v               v
                  uncertain_items     generated Skills
                                             |
                                             v
                                      聊天检索切片
```

`raw_sources` 保留证据，`persona_items` 是关联证据的结构化解释，Skill 是记忆变化后可以重建的运行时产物。聊天记录可能提供新线索，但不会自动变成已确认记忆。

详细说明见 [架构文档](docs/architecture.zh-CN.md)。

## 目录结构

```text
backend/   FastAPI 接口、数据结构、存储、工作流和运行时安全门
frontend/  Next.js App Router 工作台
desktop/   Electron 开发壳
scripts/   安装、启动、依赖准备和仓库检查脚本
tests/     可重复运行的回归与策略检查
docs/      架构、启动、桌面和声音边界文档
```

## 隐私与安全

不要提交 `.env`、API Key、人物档案、原始个人资料、数据库、日志、模型权重或音视频参考文件。仓库卫生检查会拦截主要的发布残留。处理敏感资料或将后端部署到 localhost 以外前，请阅读 [SECURITY.md](SECURITY.md)。

## 参与贡献

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。修改记忆、分类、聊天或声音流程时，必须保留原始证据、来源归属、用户纠正和明确授权。

## 许可证

本项目使用 [PolyForm Noncommercial License 1.0.0](LICENSE)。

个人、教育、研究和其他非商业用途可按许可证使用；商业使用需要另行获得授权。这是非商业源码可用许可证，不是 OSI 认可的开源许可证。
