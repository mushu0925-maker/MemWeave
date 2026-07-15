# MemWeave

[简体中文](README.zh-CN.md)

> 把散落在文字、照片和声音里的碎片，整理成记忆。

MemWeave is a local-first, evidence-grounded persona memory platform. It preserves original material first, turns supported evidence into structured A-M persona items, lets users review uncertain or sensitive interpretations, and generates bounded runtime Skills for chat and authorized voice output.

The project is designed for traceable memory organization. It does not claim to resurrect, clone, or replace a real person, and model inference or chat content is not treated as confirmed fact by default.

## What It Includes

- Raw-first ingestion for text, documents, images, audio, video, and guided interviews.
- Traceable A-M persona libraries covering facts, language, emotion, values, relationships, decisions, boundaries, and voice features.
- Review actions for uncertain material: keep, correct, downrank, hide, or forget.
- Regenerable Skill versions and bounded retrieval for chat.
- OpenAI-compatible provider configuration with model discovery and manual model-name fallback.
- Optional OCR, ASR, Supabase login entry, SQLite document storage, MCP read-only tools, and authorized IndexTTS2 voice output.
- A Chinese/English toggle for primary workspace labels, a responsive web workspace, and a Windows development Electron shell.

## Current Status

MemWeave is a working local single-user MVP and source repository. Core ingestion, evidence review, Skill generation, chat, storage, MCP, integrity checks, and voice safety boundaries are implemented.

The following boundaries are intentional and should be understood before deployment:

- External AI, OCR, ASR, and voice generation are disabled or unconfigured by default.
- The backend does not provide production authentication or tenant isolation. Do not expose it directly to the public internet.
- JSON is the default local store; SQLite document storage is optional.
- The Electron integration is a development shell, not an installer or auto-updating desktop release.
- IndexTTS2 is an optional external adapter. Model weights and reference/generated audio are not included.

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

The setup script creates `backend/.venv`, installs Python and Node dependencies, and creates local `.env` files from the sanitized examples when they do not already exist.

Expected local URLs:

- Web app: `http://127.0.0.1:3000` (or fallback port 3001-3003)
- API docs: `http://127.0.0.1:8000/docs`

Configure an OpenAI-compatible provider from Settings only when you want model-backed features. See [Getting Started](docs/getting-started.md) for manual setup and troubleshooting.

## Development Desktop Shell

After setup:

```powershell
npm run client:check
npm run client:start
```

This starts the local backend and frontend inside Electron. It does not create an installer. See [Desktop Shell](docs/desktop-shell.md).

## Verification

Run backend, policy, model-discovery, desktop, and repository-hygiene checks:

```powershell
npm test
```

Run frontend checks:

```powershell
cd frontend
npm run typecheck
npm run lint
npm run build
```

## Architecture

```text
raw_sources -> source_segments -> persona_items (A-M)
                          |             |
                          v             v
                  uncertain_items   generated Skills
                                           |
                                           v
                                  retrieved chat slices
```

Raw sources are the evidence record. Persona items are structured interpretations. Skills are regenerable runtime artifacts. Chat records are conversation history and may produce candidate evidence, but they are not confirmed facts automatically.

See [Architecture](docs/architecture.md) and the [Chinese architecture note](docs/architecture.zh-CN.md).

## Repository Layout

```text
backend/   FastAPI API, schemas, stores, workflows, and runtime guards
frontend/  Next.js App Router workspace
desktop/   Electron development shell
scripts/   Setup, startup, dependency, and hygiene utilities
tests/     Deterministic regression and policy smoke checks
docs/      Architecture, startup, desktop, and voice-boundary notes
```

## Security and Privacy

Do not commit `.env`, API keys, profiles, raw personal material, databases, logs, model weights, or audio/video references. The repository hygiene check enforces the most important release exclusions. Review [SECURITY.md](SECURITY.md) before exposing any service or handling sensitive material.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Changes to memory, classification, chat, or voice behavior should preserve raw evidence, source attribution, user correction controls, and explicit consent boundaries.

## License

MemWeave is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE).

Personal, educational, research, and other noncommercial use is permitted under the license. Commercial use requires separate authorization from the licensor. This is a source-available noncommercial license and is not an OSI-approved open-source license.
