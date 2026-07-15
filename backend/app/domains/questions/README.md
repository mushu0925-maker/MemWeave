# questions

## Current Answer Flow

Current implementation note: question answers and keep/correct uncertain item actions now share the same raw_source-first rule. Question answers use `question_answer_workflow.py`; keep/correct actions use `uncertainty_action_workflow.py`. In both paths, classification success is required before persona_items are created.

```text
schema: app/schemas/clarification.py
store: app/services/uncertainty_store.py
question seed workflow: app/workflows/uncertainty_workflow.py
answer workflow: app/workflows/question_answer_workflow.py
query API: GET /api/v1/question-targets
answer API: POST /api/v1/question-targets/{question_id}/answer
storage: question_targets.json
```

中文备注：
```text
用户回答待确认问题时，不会直接写成结论。
系统先把回答保存为 raw_source，再复用 A-M 分类流程。
分类成功后才保存 persona_items，并把 question_target 以及关联 uncertain_item 标记为 resolved。
分类失败时，回答原数据仍保留，question_target 保持 open，不生成本地保底 persona_items。
keep / correct 已在 uncertainty_action_workflow 中接入 raw_source-first 分类闭环；downrank / hide / forget 只更新 use_policy。
```

Owns adaptive targeted questions generated from A-M gaps and uncertainty records.

中文备注：

```text
questions 不做固定问卷。
每个问题都要有 target_group、target_library_key、reason 和 expected_evidence_type。
用户回答必须先保存为 raw_source，再重新 classification。
```

Current implementation:

```text
schema: app/schemas/clarification.py
store: app/services/uncertainty_store.py
workflow seed: app/workflows/uncertainty_workflow.py
query API: app/api/v1/uncertainty.py -> GET /api/v1/question-targets
storage: question_targets.json
```

中文备注：

```text
当前已实现的是“coverage_warnings 生成待追问目标并可查询/展示”。
还没有实现用户回答提交。
后续回答必须先保存为 raw_source，再走 A-M classification。
```
