# MemWeave（忆织）架构说明

## 产品边界

MemWeave 用来整理个人记忆资料，把原始证据转成可追溯的结构化解释，再生成受约束的聊天与声音运行时产物。它不是身份替代系统，生成内容不能声称自己是真实本人、具有意识或已经“复活”，也不能把没有证据的内容说成事实。

## 数据主线

```text
raw_sources
    -> source_segments
        -> persona_items（A-M）
            -> generated Skill versions
                -> selected runtime slices
                    -> chat reply
```

- `raw_sources` 保存原始或提取后的证据。
- `source_segments` 记录相关片段和人物归属状态。
- `persona_items` 保存 A-M 结构化解释，并关联来源、置信度、稳定性、范围和风险。
- `uncertain_items` 与 `question_targets` 保存不清楚、冲突、敏感或低置信度内容，等待用户处理。
- `skills` 是可重新生成的运行时产物，不是记忆真相来源。
- `chat_records` 是对话历史；聊天中出现的新信息默认只是候选。

## A-M 人格记忆库

| 分组 | 内容 |
| --- | --- |
| A | 事实与经历 |
| B | 语言风格 |
| C | 情绪反应 |
| D | 性格特征 |
| E | 价值观与世界观 |
| F | 关系模式 |
| G | 决策逻辑 |
| H | 冲突与防御 |
| I | 关心与陪伴 |
| J | 场景反应 |
| K | 成长与变化 |
| L | 边界与置信度 |
| M | 声音与说话特征 |

## 后端

FastAPI 后端分为 API 路由、Pydantic 数据结构、单域 Store/Service 和跨域 Workflow。

- API 路由负责传输层参数和 `/api/v1` 资源。
- Store 只管理一种记录族的持久化。
- Workflow 协调摄取、问题回答、不确定项处理、Skill 生成和聊天候选等跨域操作。
- 运行时安全门阻止隐藏、遗忘、无证据或归属错误的内容进入聊天和 Skill。

默认存储是本地 JSON。可选 SQLite 模式保存同样的 JSON 文档，它不是面向多用户的规范化数据库设计。

## 前端

Next.js 工作台包含五条活动主流程：

- Dashboard：创建/选择人物并添加原始资料。
- Library：检查证据、Persona 条目、不确定项和 Skill 版本。
- Chat：检索有限记忆切片，并可选生成授权声音。
- Interview：先把访谈答案保存成 raw source，再进入分类。
- Settings：配置模型供应商、功能开关、存储与诊断。

旧 Translate 页面已经从公开主线源码中移除。

## 模型与声音边界

模型调用使用兼容 OpenAI 协议的接口，每项功能可以配置独立 Base URL、API Key 和模型名。模型发现只是辅助，始终保留手动模型名输入。

外部 AI 默认关闭。提取或分类失败时仍要保留 raw source，本地规则也不能冒充正式模型蒸馏成功。

M 组只保存声音/说话特征描述，不等于声音克隆。可选 IndexTTS2 是独立适配器，必须有授权参考、确认的来源归属、明确生成同意和固定 `reply_text`。模型权重与音频资产不进入本仓库。

## 部署边界

当前后端面向本地单用户。公网部署前至少需要补齐鉴权、多租户隔离、生产存储、上传限制、TLS、密钥管理和运维监控。
