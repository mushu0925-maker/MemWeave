# Uncertainty

This domain holds interpretations that are unclear, low-confidence, conflicting, sensitive, unsupported, or painful. It is a review queue, not a trash folder and not part of the stable personal library.

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

## Actions

| Action | Result |
| --- | --- |
| `keep` | Resolve the item, set `use_policy=usable_evidence`, save the claim as a `manual_override` raw source, then run A-M classification. |
| `correct` | Resolve the item, save the corrected claim as a `manual_override` raw source, then run A-M classification. |
| `downrank` | Resolve the item with `use_policy=low_confidence_context_only`. |
| `hide` | Keep the item for audit but set `use_policy=exclude_from_chat_and_skill_keep_for_audit`. |
| `forget` | Set `use_policy=do_not_use_for_chat_or_skill`. |

Keep and correct may create persona items only after classification succeeds. A failed classification keeps the raw source and diagnostics; it does not fabricate fallback persona items. Downrank, hide, and forget update policy and state only.

None of these actions deletes the original raw source or automatically regenerates a Skill. Chat retrieval and Skill generation must read `use_policy` and respect every decision.

中文：Uncertainty 保存需要用户确认或处理的候选记忆。Keep/Correct 会把确认文本先保存为 raw source，分类成功后才可以创建 persona item；降权、隐藏和遗忘只改状态与 `use_policy`。所有运行时消费者都必须遵守这些策略。
