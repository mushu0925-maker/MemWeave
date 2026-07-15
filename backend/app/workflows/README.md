# Workflows

This directory is for cross-domain orchestration.

中文备注：

```text
workflow 负责串联多个 domain。
router 不应直接写复杂流程。
domain 不应反向调用 workflow。
```

Target workflows:

```text
ingest_workflow
reextract_workflow
question_answer_workflow
chat_workflow
skill_generation_workflow
```

Current status:

```text
ingest_workflow.py is active.
Existing ingest orchestration has been moved out of app/api/v1/ingest.py.
app/api/v1/ingest.py should remain a thin HTTP adapter.
raw source reextract temporarily reuses ingest workflow helpers until reextract_workflow.py is created.
uncertainty_workflow.py is active for turning coverage_warnings into persistent uncertain_items and question_targets.
question_answer_workflow.py is active for saving user answers as raw_sources and reclassifying them into A-M persona_items.
uncertainty_action_workflow.py is active for applying keep/correct/downrank/hide/forget decisions to uncertain_items. keep/correct save a manual_override raw_source and try A-M classification; downrank/hide/forget only update use_policy. No action deletes raw_sources, fabricates fallback persona_items, or triggers Skill regeneration.
chat_candidate_workflow.py is active for judging third-person chat messages before saving approved memory candidates as chat raw_sources plus uncertain_items/question_targets; it does not create persona_items.
persona_chat.py currently applies uncertainty `use_policy` during chat retrieval: hidden/forgotten sources are excluded, corrected claims are preferred, and downranked claims are kept as low-confidence context only.
skill_generation_workflow.py is active for generating a V2 Skill preview from existing raw_sources, persona_items, uncertain_items, and question_targets without mutating stored data.
```

中文备注：
```text
这里已经不只是空目录。
第一段已迁移的是 ingest workflow：先保存 raw_source，再调用 A-M 分类，再保存 persona_items。
第二段已接入的是 uncertainty workflow：分类成功后把 coverage_warnings 写成待确认问题，不写成 persona_items。
第三段已接入的是 question_answer workflow：用户回答待确认问题时，先把回答保存成 raw_source，再复用 A-M 分类；分类成功才关闭问题，分类失败则保留 raw_source 并保持问题打开。
第四段已接入的是 chat candidate workflow：第三者聊天里的用户补充先经过基础无效过滤和 AI 判断；判断通过后才保存为 source_type=chat 的 raw_source，再进入 uncertain_items / question_targets 待确认区；不会直接写 persona_items。AI 不可用或判断失败时默认不入待确认区。
第五段已接入的是 chat retrieval use_policy：聊天上下文会读取 uncertain_item 的处理结果；隐藏/遗忘的 source 不进入聊天检索，纠正文案优先进入上下文，降权内容只作为低置信上下文。
第六段已接入的是 Skill generation preview：workflow 读取 stores，domains/skills 负责纯算法打包，生成 evidence units、usage matrix、cap rules、ranking scores、caution report、question backlog 和 audit report；当前不持久化生成结果、不调用 AI。
后续不要把 uncertainty、question_targets、chat retrieval、Skill generation 的编排重新写进 router。
```
