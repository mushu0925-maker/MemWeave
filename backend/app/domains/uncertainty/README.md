# uncertainty

Owns unclear, low-confidence, conflicting, sensitive, unsupported, or painful memory candidates.

中文备注：
```text
uncertainty 承接不确定项。
它不是垃圾桶，也不是稳定个人库。
它的任务是保存需要用户确认、纠正、降权、隐藏或遗忘的候选记忆。
```

Current implementation:

```text
schema: app/schemas/clarification.py
store: app/services/uncertainty_store.py
workflow: app/workflows/uncertainty_workflow.py
action workflow: app/workflows/uncertainty_action_workflow.py
query API: app/api/v1/uncertainty.py -> GET /api/v1/uncertain-items
action API: app/api/v1/uncertainty.py -> POST /api/v1/uncertain-items/{item_id}/action
storage: uncertain_items.json
```

Action rules:

Implementation note: keep/correct preserve the confirmed text as a manual_override raw_source and then reuse A-M classification. Successful classification may create persona_items; failed classification keeps the raw_source and diagnostics without fabricating fallback persona_items. downrank/hide/forget only update status, metadata, and use_policy.

```text
keep: mark the uncertain item resolved, record use_policy=usable_evidence, save the claim as a manual_override raw_source, then try A-M classification.
correct: mark resolved, record the user's corrected_claim, save the correction as a manual_override raw_source, then try A-M classification.
downrank: mark resolved and record use_policy=low_confidence_context_only.
hide: mark hidden and record use_policy=exclude_from_chat_and_skill_keep_for_audit.
forget: mark forgotten and record use_policy=do_not_use_for_chat_or_skill.
```

中文备注：
```text
这些动作只更新 uncertain_item 和关联 question_target 的状态、metadata、use_policy。
它们不删除 raw_source，不生成本地保底 persona_items，也不自动触发 Skill regeneration。
后续 chat retrieval 和 Skill generation 必须读取 use_policy，不能绕过隐藏、遗忘、降权、纠正策略。
```
