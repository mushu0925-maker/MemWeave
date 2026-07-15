# Persona Items

Persona items are the structured A-M entries used by the Library, Skill generation, and chat retrieval.

Each item should point to a `source_id` and useful evidence quote whenever possible. State changes such as correction, confirmation, downranking, hiding, and forgetting need explicit rules so runtime consumers cannot ignore the user's decision.

中文：persona items 是 A-M 个人库条目。每条应尽量追溯到 `source_id` 和证据引用；纠正、确认、降权、隐藏和遗忘必须有可执行的状态规则。
