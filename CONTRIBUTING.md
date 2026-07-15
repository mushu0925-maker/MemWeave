# Contributing to MemWeave

Contributions are welcome when they make the project easier to understand, safer to use, or more reliable without weakening the evidence trail.

Before changing a memory, classification, chat, or voice workflow, identify which data layer owns the change. Raw sources, persona items, generated Skills, chat records, and uncertain items have different jobs and should not be merged for convenience.

## Development Setup

1. Install Node.js 20+ and Python 3.11+ on Windows.
2. Run `npm run setup` from the repository root.
3. Run `npm run dev` and verify the web app and API docs open.

## Before Submitting a Change

Run:

```powershell
npm test
cd frontend
npm run typecheck
npm run lint
npm run build
```

Do not commit local `.env` files, API keys, profile data, raw personal material, databases, logs, model weights, reference audio, or generated media.

## Rules That Changes Must Preserve

- Preserve raw evidence before classification.
- Classification failure must not erase raw material.
- Persona items should link to source evidence whenever possible.
- Generated Skills must remain regenerable from structured items and selected evidence.
- Chat discoveries are candidates until the user confirms them.
- Hidden, forgotten, deleted, or `do_not_use` material must not enter runtime retrieval.
- Voice generation requires explicit authorization and may only read fixed generated text.

## Pull Requests

Keep a pull request focused. Explain what changes for the user, which data layers are involved, what you verified, and what still remains uncertain. Add or update deterministic tests when behavior changes.

By contributing, you agree that your contribution is provided under the repository's PolyForm Noncommercial License 1.0.0.
