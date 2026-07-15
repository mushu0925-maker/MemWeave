# Domains

These folders document the intended business boundaries. Most runtime code still lives in `app/api/v1`, `app/schemas`, and `app/services`, so this directory is not a second application entry point.

A domain should own rules for one area only. Cross-domain sequencing belongs in `app/workflows`; provider, storage, media, and logging adapters belong in `app/infrastructure`. Move runtime behavior into a domain only as part of a focused migration.

中文：这里记录单个领域的职责边界。每个领域只处理自己的规则；跨领域编排放在 `app/workflows`，技术适配放在 `app/infrastructure`。

Documented domains:

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
