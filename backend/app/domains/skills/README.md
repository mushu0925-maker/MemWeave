# Skills

A Skill is a runtime package built from reviewed persona items, boundary rules, and selected evidence. It is not source data and can be regenerated whenever the personal library changes.

## Current V2 Packager

`generation.py` contains pure packaging rules. It turns persona items into evidence units, applies user-policy gates, usage and cap rules, and ranking scores.

The packager does not read or write storage, call an AI provider, or mutate raw sources, persona items, uncertain items, or question targets.

中文：Skill 是从已审核个人库生成的运行时产物，不是事实源。`generation.py` 只做纯打包和排序，不读写存储、不调用 AI、不修改任何记忆记录。
