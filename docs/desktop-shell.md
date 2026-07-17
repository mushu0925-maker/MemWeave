# Desktop Development Shell

The Electron development shell opens the source checkout's local MemWeave services in a desktop window. It remains separate from the packaged Windows runtime.

## Start

```powershell
npm run setup
npm run client:check
npm run client:start
```

The launcher uses `backend/.venv/Scripts/python.exe` when it exists, then falls back to Python from PATH. Node is resolved from PATH. Electron starts or reuses the local backend and frontend and writes its logs under `logs/`.

The readiness check requests the Next.js static assets referenced by the page. A server that returns only HTML while its CSS or JavaScript is broken is not considered ready.

## Optional Voice Adapter

If an external IndexTTS2 checkout and checkpoints exist under `indextts2/index-tts`, the shell can try to start it. Missing weights or runtime dependencies produce an optional warning and do not stop the rest of MemWeave.

No IndexTTS2 source, weights, reference audio, or generated output is included in this repository.

The automatic layout also needs a compatible `indextts2/server.py` adapter and matching backend environment settings. See [Authorized Voice Output](authorized-voice.md) for the exact layout, adapter contract, and readiness checks.

## Packaged Windows Runtime

The v0.2.0 packaging flow bundles Electron, a Next.js standalone server, and a PyInstaller backend into an unsigned Windows x64 NSIS installer. It does not bundle IndexTTS2 weights, user data, credentials, code signing, or automatic updates.

See [Windows Installer](windows-installer.md) for build commands, installed data paths, backups, and uninstall behavior.
