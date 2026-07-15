# skills

Owns generated runtime Skill artifacts.

中文备注：

```text
Skill 是运行态产物，不是源数据。
Skill 应从 persona_items、边界库和选定证据生成。
个人库变化后 Skill 应可重新生成。
```

Current V2 implementation:

```text
generation.py owns pure Skill packaging rules.
It turns persona_items into evidence units, applies user policy gates, usage matrix, cap rules, and ranking scores.
It does not read or write storage directly.
It does not call AI.
It does not mutate raw_sources, persona_items, uncertain_items, or question_targets.
```
