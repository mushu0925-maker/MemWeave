# Getting Started

The automated setup is the recommended path. The manual commands below are mainly for debugging an installation or working around a local environment issue.

## Prerequisites

- Windows 10 or 11
- PowerShell 5.1 or newer
- Node.js 20 or newer
- Python 3.11 or newer

## Automated Setup

From the repository root:

```powershell
npm run setup
```

The script performs these steps:

1. Creates `backend/.venv` when missing.
2. Installs `backend/requirements.txt`.
3. Runs `npm ci` in `frontend` and the repository root.
4. Copies sanitized environment examples to local `.env` files only when those files do not exist.

Use `npm run setup -- -SkipDesktop` when you only need the web application.

## Manual Setup

```powershell
python -m venv backend/.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

cd frontend
npm ci
cd ..

npm ci
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.local.example frontend\.env.local
```

The generated `.env` files are local configuration and must not be committed.

## Start the Web Application

```powershell
npm run dev
```

The launcher reuses a compatible backend when one is already running; otherwise it starts FastAPI on port 8000. Next.js starts on port 3000 or a fallback from 3001-3003. The frontend is considered ready only when both the root page and its referenced `/_next/static` assets respond successfully.

## Configure Models

External AI is disabled by default. Open Settings and configure only the capabilities you plan to use:

- Chat / persona classification
- Vision OCR
- ASR

Chat, persona classification, vision OCR, and ASR use OpenAI-compatible provider settings. Some providers do not implement model discovery, so the Settings page always accepts a manually entered model name.

Authorized voice generation is separate. It uses an external IndexTTS2 adapter configured through `backend/.env`; Settings displays its status but does not edit those fields. See [Authorized Voice Output](authorized-voice.md).

## Verify the Checkout

```powershell
npm test

cd frontend
npm run typecheck
npm run lint
npm run build
```

## Common Problems

- `Backend dependencies are missing`: run `npm run setup` and confirm `backend/.venv/Scripts/python.exe` exists.

- `Missing Next.js binary`: run `npm ci` inside `frontend`.

- Frontend reports not ready while HTML responds: inspect `logs/frontend-dev.err.log`. The launcher deliberately rejects HTML-only responses when Next.js static assets are unavailable.

- Port already in use: stop the unrelated process or choose different ports when calling `scripts/start-dev.ps1`.
