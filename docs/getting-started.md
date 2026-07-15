# Getting Started

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

The script:

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

Never commit the generated `.env` files.

## Start the Web Application

```powershell
npm run dev
```

The launcher reuses a compatible backend when available, otherwise starts FastAPI on port 8000. It starts Next.js on port 3000 or a fallback port from 3001-3003. Frontend readiness requires both the root HTML and referenced `/_next/static` assets to respond successfully.

## Configure Models

External AI is disabled by default. Open Settings and configure only the capabilities you intend to use:

- Chat / persona classification
- Vision OCR
- ASR
- Authorized voice generation

The provider must expose an OpenAI-compatible API. Model discovery may be unavailable on some providers; a manual model name is always accepted.

## Verify the Checkout

```powershell
npm test

cd frontend
npm run typecheck
npm run lint
npm run build
```

## Common Problems

`Backend dependencies are missing`: run `npm run setup` and confirm `backend/.venv/Scripts/python.exe` exists.

`Missing Next.js binary`: run `npm ci` inside `frontend`.

Frontend reports not ready while HTML responds: inspect `logs/frontend-dev.err.log`. The launcher deliberately rejects HTML-only responses when Next.js static assets are unavailable.

Port already in use: stop the unrelated process or choose different ports when calling `scripts/start-dev.ps1`.
