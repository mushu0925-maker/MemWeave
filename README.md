# MemWeave

[简体中文](README.zh-CN.md)

> 把散落在文字、照片和声音里的碎片，整理成记忆。

Personal memories rarely arrive as a clean biography. They are spread across chat exports, notes, photographs, recordings, documents, and conversations.

I built MemWeave to keep those materials intact, extract details that can be traced back to their source, and let the user decide what should become part of a structured memory profile. The reviewed profile can then be used to prepare chat context or, with explicit permission, read a fixed reply through an external voice model.

MemWeave does not treat model output as fact. It does not claim to recreate or replace a real person, and it does not present generated replies as that person's literal words.

## How It Works

1. Save the original text or uploaded file before running classification.
2. Split useful material into attributed source segments.
3. Turn supported details into A-M persona items covering facts, language, emotions, values, relationships, decisions, boundaries, and speech features.
4. Send unclear or sensitive interpretations to review instead of quietly accepting them.
5. Generate a replaceable Skill and retrieve only the parts needed for the current chat message.

Users can keep, correct, downrank, hide, or forget uncertain material. A correction goes back through the evidence flow; hidden or forgotten material is excluded from chat and Skill generation.

## What Is Implemented

- Ingestion for text, documents, images, audio, video, and guided interview answers.
- Source-linked A-M persona libraries with confidence, stability, scope, and risk metadata.
- Review queues for uncertain material and targeted follow-up questions.
- Regenerable Skill previews, saved Skill versions, and message-level chat retrieval.
- OpenAI-compatible provider settings with model discovery and manual model-name entry.
- Optional OCR, ASR, SQLite document storage, read-only MCP tools, Supabase login entry, and authorized IndexTTS2 output.
- A responsive Next.js workspace, primary-label Chinese/English switching, and an Electron development shell for Windows.
- Deterministic regression, policy, desktop, repository-hygiene, and CI checks.

## Current Limits

MemWeave is a working local, single-user MVP. It is suitable for development and portfolio review, but it is not a hosted production service or a packaged desktop product.

- External AI, OCR, ASR, and voice generation are disabled or unconfigured by default.
- The FastAPI backend has no production authentication or tenant isolation. Do not expose it directly to the public internet.
- JSON is the default local store. The optional SQLite mode stores the same document-shaped data; it is not a multi-user relational design.
- The Electron app is a development shell with no installer, code signing, automatic updates, or bundled runtimes.
- IndexTTS2 is an optional external adapter. This repository contains no model weights, voice references, or generated audio.

## Quick Start

Requirements:

- Windows 10 or 11 with PowerShell
- Node.js 20 or newer
- Python 3.11 or newer

From the repository root:

```powershell
npm run setup
npm run dev
```

The setup script creates `backend/.venv`, installs the Python and Node dependencies, and copies the sanitized environment examples only when local `.env` files do not already exist.

Default addresses:

- Web app: `http://127.0.0.1:3000` (or fallback port 3001-3003)
- API docs: `http://127.0.0.1:8000/docs`

Configure an OpenAI-compatible provider in Settings only when you need model-backed features. See [Getting Started](docs/getting-started.md) for manual setup and troubleshooting.

IndexTTS2 uses a separate local adapter. Read [Authorized Voice Output](docs/authorized-voice.md) before enabling it.

## Desktop Development Shell

After setup:

```powershell
npm run client:check
npm run client:start
```

These commands start the local backend and frontend inside Electron. They do not build an installer. See [Desktop Shell](docs/desktop-shell.md).

## Verification

Run the backend, policy, model-discovery, desktop, and repository-hygiene checks:

```powershell
npm test
```

Run the frontend checks:

```powershell
cd frontend
npm run typecheck
npm run lint
npm run build
```

## Data Flow

```text
raw_sources -> source_segments -> persona_items (A-M)
                          |             |
                          v             v
                  uncertain_items   generated Skills
                                           |
                                           v
                                  retrieved chat slices
```

The raw source is the evidence record. A persona item is an interpretation linked to that evidence. A Skill is a runtime package that can be rebuilt when the reviewed memory changes. Chat history may suggest new evidence, but it does not become confirmed memory automatically.

See [Architecture](docs/architecture.md) and the [Chinese architecture note](docs/architecture.zh-CN.md).

## Repository Layout

```text
backend/   FastAPI APIs, schemas, stores, workflows, and runtime guards
frontend/  Next.js App Router workspace
desktop/   Electron development shell
scripts/   Setup, startup, dependency, and repository checks
tests/     Deterministic regression and policy checks
docs/      Architecture, setup, desktop, and voice-boundary notes
```

## Security and Privacy

Do not commit `.env` files, API keys, profiles, personal source material, databases, logs, model weights, or audio/video references. The repository hygiene check covers the main release exclusions. Read [SECURITY.md](SECURITY.md) before handling sensitive material or deploying the backend beyond localhost.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Changes to memory, classification, chat, or voice behavior must preserve source evidence, attribution, correction controls, and explicit consent.

## License

MemWeave uses the [PolyForm Noncommercial License 1.0.0](LICENSE).

Personal, educational, research, and other noncommercial use is permitted under the license. Commercial use requires separate authorization from the licensor. This is a source-available noncommercial license, not an OSI-approved open-source license.
