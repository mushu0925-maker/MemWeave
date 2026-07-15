# Workflows

Workflows coordinate operations that touch more than one domain. API routers should remain thin HTTP adapters, and domains must not call back into workflows.

## Active Flows

- `ingest_workflow.py` saves the raw source first, runs A-M classification, then stores persona items. Raw-source re-extraction currently reuses its helpers until a dedicated re-extraction workflow is introduced.
- `uncertainty_workflow.py` turns classification coverage warnings into persistent uncertain items and question targets, not persona items.
- `question_answer_workflow.py` saves an answer as a raw source and reclassifies it. The question closes only after classification succeeds; otherwise the source remains and the question stays open.
- `uncertainty_action_workflow.py` applies keep, correct, downrank, hide, and forget. Keep/correct save a `manual_override` raw source and attempt classification. The other actions change `use_policy` only. No action deletes raw sources, fabricates fallback persona items, or regenerates a Skill automatically.
- `chat_candidate_workflow.py` filters and evaluates third-person chat additions. Accepted candidates are stored as `source_type=chat` raw sources plus uncertainty/question records; they do not become persona items directly. If AI judgment is unavailable or fails, the candidate is not admitted.
- `persona_chat.py` applies uncertainty policy during retrieval: hidden and forgotten sources are excluded, corrections are preferred, and downranked material is low-confidence context only.
- `skill_generation_workflow.py` reads the current stores and builds a V2 Skill preview without mutating memory data. The pure packager remains under `domains/skills`.

中文：Workflow 负责串联多个领域。当前摄取、不确定项、问题回答、聊天候选和 Skill 预览都有独立编排。失败时必须保留原始证据，不得伪造保底 persona item，也不得把这些跨域流程重新塞回 router。
