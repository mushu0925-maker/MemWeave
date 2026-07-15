# MemWeave Architecture

## Product Boundary

MemWeave organizes personal memory material into traceable structured interpretations and bounded runtime artifacts. It is not an identity replacement system. Generated chat and voice output must not claim literal identity, consciousness, resurrection, or unsupported facts.

## Source-of-Truth Model

```text
raw_sources
    -> source_segments
        -> persona_items (A-M)
            -> generated Skill versions
                -> selected runtime slices
                    -> chat reply
```

- `raw_sources` preserve original or extracted evidence.
- `source_segments` identify relevant excerpts and attribution state.
- `persona_items` store structured A-M interpretations with source links, confidence, stability, scope, and risk.
- `uncertain_items` and `question_targets` hold unclear, conflicting, sensitive, or low-confidence material for review.
- `skills` are regenerable runtime artifacts, not canonical memory.
- `chat_records` are conversation history. New claims remain candidates until confirmed.

## A-M Persona Libraries

| Group | Area |
| --- | --- |
| A | Facts and events |
| B | Language style |
| C | Emotional response |
| D | Personality traits |
| E | Values and worldview |
| F | Relationship modes |
| G | Decision logic |
| H | Conflict and defense |
| I | Care and companionship |
| J | Scenario response |
| K | Growth and change |
| L | Boundaries and confidence |
| M | Voice and speech features |

## Backend

The FastAPI backend is split into API routers, Pydantic schemas, domain services/stores, and orchestration workflows.

- API routers validate transport-level input and expose `/api/v1` resources.
- Stores own persistence for one record family.
- Workflows coordinate cross-domain operations such as ingestion, question answers, uncertainty actions, Skill generation, and chat candidates.
- Runtime guards prevent hidden, forgotten, unsupported, or incorrectly attributed material from entering chat and Skill generation.

Local JSON files are the default persistence backend. The optional SQLite mode stores the same JSON documents in SQLite; it is not a normalized multi-user schema.

## Frontend

The Next.js workspace provides five active workflows:

- Dashboard: create/select profiles and add raw material.
- Library: inspect evidence, persona items, uncertainty, and Skill versions.
- Chat: retrieve bounded memory slices and optionally generate authorized voice output.
- Interview: save guided answers as raw sources before classification.
- Settings: configure providers, feature flags, storage, and diagnostics.

The former Translate page is intentionally excluded from the active source tree.

## AI Provider Boundary

Provider calls use an OpenAI-compatible interface. Each feature can use its own Base URL, API key, and model name. Model discovery is advisory and always retains a manual model-name fallback.

External AI features are disabled by default. Raw material must remain stored when extraction or classification fails, and local fallback rules must not be presented as successful model distillation.

## Voice Boundary

Voice feature storage describes speech characteristics; it is not voice cloning. Optional IndexTTS2 generation is a separate adapter and requires an authorized reference, confirmed source attribution, explicit generation consent, and fixed `reply_text`. Model weights and audio assets stay outside this repository.

## Deployment Boundary

The current backend is intended for local single-user use. A public deployment needs authentication, tenant isolation, production storage, upload limits, TLS, secret management, and operational monitoring before it can be considered safe.
