# MemWeave Architecture

This document explains the parts of MemWeave that matter when changing the code. The central rule is simple: keep the original material, keep interpretations linked to it, and treat anything generated for chat as replaceable output.

MemWeave is not an identity replacement system. Chat and voice output must not claim to be a real person, claim consciousness or resurrection, or present unsupported details as fact.

## Data Flow

```text
raw_sources
    -> source_segments
        -> persona_items (A-M)
            -> generated Skill versions
                -> selected runtime slices
                    -> chat reply
```

- `raw_sources` keep the submitted material and extracted content.
- `source_segments` mark the excerpts that matter and record who they belong to.
- `persona_items` store source-linked A-M interpretations with confidence, stability, scope, and risk.
- `uncertain_items` and `question_targets` hold unclear, conflicting, sensitive, or low-confidence interpretations for review.
- Generated Skills package reviewed material for runtime use and can be rebuilt at any time.
- `chat_records` keep conversation history. A new claim from chat remains a candidate until the user confirms it.

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

The FastAPI backend separates HTTP handling from storage, domain rules, and cross-domain workflows.

- API routers validate requests and expose `/api/v1` resources.
- Stores persist one record family at a time.
- Workflows coordinate operations that cross record families, including ingestion, question answers, uncertainty actions, Skill generation, and chat candidates.
- Runtime guards keep hidden, forgotten, unsupported, or incorrectly attributed material out of chat and Skill generation.

Local JSON files are the default persistence backend. The optional SQLite mode stores the same JSON documents in SQLite; it is not a normalized multi-user schema.

## Frontend

The Next.js workspace is organized around five user tasks:

- Dashboard: create/select profiles and add raw material.
- Library: inspect evidence, persona items, uncertainty, and Skill versions.
- Chat: retrieve only the memory slices needed for the current message and optionally generate authorized voice output.
- Interview: save guided answers as raw sources before classification.
- Settings: configure providers, feature flags, storage, and diagnostics.

The former Translate page is not part of the active source tree.

## External Models

Provider calls use an OpenAI-compatible interface. Chat/classification, vision OCR, and ASR can each use their own Base URL, API key, and model name. Model discovery helps populate choices, but manual model-name entry remains available when a provider does not expose discovery.

External AI features are disabled by default. If extraction or classification fails, the raw material stays stored. Local fallback rules must not be reported as a successful model-based distillation.

## Voice Output

Group M stores descriptions of speech characteristics; that alone is not voice cloning. Optional IndexTTS2 output is a separate step. It requires an authorized reference, confirmed source attribution, explicit consent for generation, and a fixed `reply_text`. Model weights and audio assets stay outside this repository.

## Before Network Deployment

The current backend is for local, single-user use. A network deployment needs authentication, tenant isolation, production storage, upload limits, TLS, secret management, and operational monitoring before it can be considered safe.
