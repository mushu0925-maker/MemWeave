# Development Desktop Shell

MemWeave includes an Electron shell for local development. It is not a packaged installer.

## Start

```powershell
npm run setup
npm run client:check
npm run client:start
```

The launcher uses `backend/.venv/Scripts/python.exe` when available, otherwise a Python interpreter from PATH. Node is resolved from PATH. The Electron process starts or reuses the local backend and frontend and keeps its own logs under `logs/`.

Frontend readiness includes referenced Next.js static assets, so an HTML-only broken development server is not accepted as ready.

## Optional Voice Adapter

If an external IndexTTS2 checkout and checkpoints exist under `indextts2/index-tts`, the shell can attempt to start it. Missing weights or runtime dependencies are treated as an optional warning; the rest of MemWeave can still start.

No IndexTTS2 source, weights, reference audio, or generated output is included in this repository.

## Packaging Boundary

The current shell has no installer builder, code signing, automatic updates, bundled Python/Node, or bundled model runtime. Those are separate distribution tasks.
