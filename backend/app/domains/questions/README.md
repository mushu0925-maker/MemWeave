# Questions

Question targets turn gaps or uncertainty in the A-M libraries into focused follow-up questions. They are not a fixed questionnaire. Each target records the group, library key, reason for asking, and expected evidence type.

## Answer Flow

1. Save the user's answer as a raw source.
2. Run the normal A-M classification flow on that source.
3. Create persona items and resolve the linked question only when classification succeeds.
4. If classification fails, keep the raw source and diagnostics, leave the question open, and do not create fallback persona items.

The keep/correct uncertainty actions follow the same raw-source-first rule through `uncertainty_action_workflow.py`. Downrank, hide, and forget change `use_policy` only.

中文：问题来自 A-M 个人库的缺口和不确定项，不是固定问卷。用户回答后，系统先保存 raw source，再走分类流程；只有分类成功才会创建 persona items 并关闭问题。

## Current Entry Points

```text
schema: app/schemas/clarification.py
store: app/services/uncertainty_store.py
question seed workflow: app/workflows/uncertainty_workflow.py
answer workflow: app/workflows/question_answer_workflow.py
query API: GET /api/v1/question-targets
answer API: POST /api/v1/question-targets/{question_id}/answer
storage: question_targets.json
```
