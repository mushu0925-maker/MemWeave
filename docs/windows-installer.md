# Windows Installer

MemWeave v0.2.0 can be built and distributed as an unsigned Windows x64 NSIS installer.

## Distribution Boundary

The installer bundles:

- Electron and its Node runtime.
- The Next.js standalone frontend and traced production dependencies.
- The FastAPI backend as a PyInstaller runtime.
- The optional local voice setup helper.

It does not bundle API keys, personal memory data, voice references, generated audio, IndexTTS2 source, or model weights. The application binds its local services to `127.0.0.1`.

The installer is not code-signed. Windows may display an unknown-publisher warning. Verify the Setup.exe SHA-256 against the value in the GitHub Release notes before running it.

## Install And Data

Run `MemWeave-0.2.0-Setup.exe` and choose an installation directory. On first launch, MemWeave starts its packaged frontend and backend and creates its writable state under:

```text
%LOCALAPPDATA%\MemWeave
```

That directory contains local configuration, JSON/SQLite data, logs, uploads, voice references, generated audio, and Electron browser state. Program files remain read-only resources.

## Backup And Import

Before moving computers or uninstalling:

1. Open Settings.
2. Choose **Export full backup**.
3. Store the ZIP in a protected location.

The Dashboard can export only the selected profile. A profile backup includes its evidence, A-M persona items, Skills, chat records, authorized voice references, and generated audio when those files are application-owned.

Backup ZIP files are not encrypted. They exclude API keys, provider credentials, model weights, program dependencies, and global AI configuration. Import first shows a profile-conflict preview, then requires either merge or import-as-new; it does not silently overwrite an existing profile.

## Uninstall

Uninstall displays a warning that local memories and settings will be deleted. Continuing removes `%LOCALAPPDATA%\MemWeave` by default, along with application logs, attachments, and generated audio. Export a backup first when the data must be retained.

## Optional Voice Setup

The installed Settings page can open the local voice setup helper. The helper requires an existing IndexTTS2 model directory containing `config.yaml`. It can obtain upstream source, create a Python environment, install dependencies, and optionally install FFmpeg, but it never downloads or copies model weights.

Voice output still requires confirmed source attribution, explicit consent, and a fixed generated `reply_text`. Read [Authorized Voice Output](authorized-voice.md) before enabling it.

## Build From Source

Requirements: Windows 10/11, PowerShell 5.1+, Node.js 20+, and Python 3.11+.

```powershell
npm ci --ignore-scripts
npm --prefix frontend ci
npm run package:setup
npm run package:win
```

`package:setup` downloads Electron from the configured mirror, verifies it against Electron's packaged `checksums.json`, and installs isolated Python packaging dependencies. `package:win` builds the frontend/backend, creates the NSIS installer, and runs the packaged-resource verifier.

Artifacts are written to:

```text
release/installers/MemWeave-0.2.0-Setup.exe
release/installers/MemWeave-0.2.0-Setup.exe.blockmap
```

Run `npm test`, frontend typecheck/lint/build, and `npm run package:verify` before publishing a release.
