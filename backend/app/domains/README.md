# Domains

This directory is the future home for single-domain business modules.

Current status:

```text
Boundary scaffold only.
Runtime code still lives in app/api/v1, app/schemas, and app/services.
Do not move behavior here without a focused migration step.
```

中文备注：

```text
这里是“领域模块”骨架，不是新的运行入口。
每个领域只处理自己的业务规则，不能直接编排跨模块流程。
跨模块流程放到 app/workflows。
技术适配放到 app/infrastructure。
```

Target domains:

```text
profiles
raw_sources
persona_items
classification
uncertainty
questions
chat
skills
voice
```
