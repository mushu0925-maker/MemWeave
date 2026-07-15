# Authorized Voice Output

MemWeave can send an already-written reply to an external IndexTTS2 service. This step is optional and disabled by default.

IndexTTS2 does not choose memories, facts, persona traits, or reply wording. MemWeave decides a fixed `reply_text` first, applies its evidence and runtime rules, and only then asks the voice adapter to read that text.

## What You Need

- A separate IndexTTS2 checkout, Python environment, and model checkpoints.
- A small HTTP adapter that exposes the contract described below.
- Voice settings in `backend/.env`.
- An authorized audio or video reference for the selected profile.
- FFmpeg only when the reference is a video.

The source repository does not include IndexTTS2, the adapter `server.py`, checkpoints, reference media, or generated audio. Follow the [upstream IndexTTS repository](https://github.com/index-tts/index-tts) for its Python, CUDA, and checkpoint setup. Upstream compatibility still depends on your hardware and installed dependencies.

## Configure the Backend

Add the following values to `backend/.env`:

```env
ENABLE_VOICE_GENERATION=true
VOICE_GENERATION_PROVIDER=indextts2
VOICE_GENERATION_BASE_URL=http://127.0.0.1:7861
VOICE_GENERATION_TIMEOUT_SECONDS=180
VOICE_REFERENCE_DIR=data/voice_references
VOICE_OUTPUT_DIR=data/voice_outputs
VOICE_VIDEO_FFMPEG_PATH=ffmpeg
VOICE_VIDEO_EXTRACT_TIMEOUT_SECONDS=120
```

`VOICE_GENERATION_BASE_URL` must be the adapter base address, without `/synthesize`, `/tts`, or `/generate`. MemWeave appends those paths itself.

Relative reference and output paths are resolved from the `backend` directory. Restart the backend or desktop shell after changing `backend/.env`; the settings are cached for the running process.

These values are not editable in the current Settings page. Settings displays adapter and FFmpeg status, while `backend/.env` remains the configuration source.

## Start the Adapter

You can manage the adapter yourself or let the Electron development shell try to start a local layout.

### Desktop-managed layout

The desktop shell expects this structure:

```text
indextts2/
  server.py
  index-tts/
    .venv/
      Scripts/python.exe
    checkpoints/
      config.yaml
      ...model files
```

`server.py` must expose a FastAPI-compatible `app`. The shell starts it with:

```text
python -m uvicorn server:app --host 127.0.0.1 --port 7861
```

In full, the adapter path is `indextts2/server.py`, and the required desktop config path is `indextts2/index-tts/checkpoints/config.yaml`.

It runs from `indextts2/`, while using the Python environment and checkpoints under `indextts2/index-tts/`. If the workspace path contains non-ASCII characters, the shell creates a temporary ASCII junction before starting the adapter.

The shell first checks `http://127.0.0.1:7861/health`. A healthy existing adapter is reused. Missing checkpoints or Python are treated as an optional warning, so the rest of MemWeave can still start.

Optional process variables are:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DESKTOP_INDEXTTS2_PORT` | `7861` | Desktop health and launch port |
| `INDEXTTS2_DEVICE` | `cuda` | Device passed to the adapter |
| `INDEXTTS2_USE_FP16` | `false` | Forwarded model option |
| `INDEXTTS2_USE_CUDA_KERNEL` | `false` | Forwarded model option |
| `INDEXTTS2_USE_DEEPSPEED` | `false` | Forwarded model option |

If you change `DESKTOP_INDEXTTS2_PORT`, update `VOICE_GENERATION_BASE_URL` to the same port.

### Manually managed adapter

The web application does not require the desktop layout. You may run any local or remote service that implements the adapter contract and point `VOICE_GENERATION_BASE_URL` to it.

Keep the service private. MemWeave sends a local reference-audio path in the request, so a remote adapter cannot use that path unless you add your own secure file-transfer layer. The current built-in flow is designed for a local adapter.

## Adapter Contract

MemWeave tries these endpoints in order:

1. `POST /synthesize`
2. `POST /tts`
3. `POST /generate`

A 404 moves to the next endpoint. Other failures are collected and returned as `IndexTTS2 adapter call failed`.

Example request:

```json
{
  "text": "fixed reply text",
  "prompt_audio": "E:/path/to/reference.wav",
  "reference_audio": "E:/path/to/reference.wav",
  "audio_path": "E:/path/to/reference.wav",
  "emotion": null,
  "return_base64": true,
  "ai_generated": true
}
```

Supported responses:

- direct `audio/*` bytes;
- RIFF/WAV bytes;
- JSON containing `audio_base64`, `audio`, or `wav_base64`;
- JSON containing `audio_url` or `url`.

The optional `/health` endpoint is used by the desktop shell. A successful health response proves that the HTTP process is reachable, not that the model can complete synthesis. Use a Voice Studio preview for the final test.

## Prepare FFmpeg for Video References

Audio references do not need FFmpeg. For video references, either put FFmpeg on `PATH`, set `VOICE_VIDEO_FFMPEG_PATH` to an executable, or run:

```powershell
npm run voice:prepare-ffmpeg
```

The script places `ffmpeg.exe` under `tools/ffmpeg/`, which is ignored by Git. MemWeave preserves the uploaded video as a raw source and creates a WAV reference for TTS. If extraction fails, the upload remains saved but voice generation stays blocked.

## Check Readiness

After restarting the backend:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/voice/status
```

For a configured adapter, look for:

```text
enabled: true
configured: true
base_url: http://127.0.0.1:7861
```

The Settings page also shows:

- IndexTTS2 enabled/configured state;
- FFmpeg availability;
- the system self-check result.

The self-check verifies configuration readiness only. It does not upload a reference or perform synthesis.

## Use Voice Studio

1. Select an active profile in Chat.
2. Upload an audio or video reference. The maximum upload size is 100 MB.
3. Confirm that you are authorized to use the reference and add a consent note.
4. For video, wait for audio extraction or retry it after configuring FFmpeg.
5. Confirm that the source segment belongs to the target person and allow `voice_reference` or `voice_generation` use.
6. Select the reference or make it the profile default.
7. Generate a preview or read an existing assistant reply.
8. Confirm consent again for that generation request.

If a generation supplies `chat_record_id`, `reply_text` must exactly match that record's `assistant_message`. Generated output is stored as AI generated and must be presented with that label.

## Common Problems

| Message or symptom | What to check |
| --- | --- |
| `Voice generation is disabled.` | Set `ENABLE_VOICE_GENERATION=true`, then restart the backend. |
| `IndexTTS2 endpoint is not configured.` | Set `VOICE_GENERATION_BASE_URL`, without an endpoint suffix, then restart. |
| `IndexTTS2 adapter call failed` | Read the endpoint details. Confirm the adapter implements at least one supported endpoint and returns audio in a supported format. |
| Port 7861 is occupied but the adapter did not respond | Stop the unrelated process or choose another port and update both desktop and backend settings. |
| Missing checkpoints or IndexTTS2 Python | Complete the desktop-managed directory layout, or start a compatible adapter yourself. |
| Adapter health passes but synthesis fails | Check adapter logs, upstream imports, checkpoint paths, device/CUDA compatibility, and the first real synthesis error. |
| Video reference is not ready | Run `npm run voice:prepare-ffmpeg`, configure another FFmpeg path, or upload audio directly. |
| Segment attribution or consent is not confirmed | Confirm the target person, attribution, consent, and permitted voice use in Voice Studio or Library. |
| `reply_text must match...` | Generate audio from the selected assistant message without editing its text. |

## Keep Runtime Files Out of Git

Do not commit:

- `backend/.env`;
- `backend/data/voice_references/`;
- `backend/data/voice_outputs/`;
- `indextts2/`;
- `tools/ffmpeg/`;
- model checkpoints, real reference media, generated samples, logs, databases, or consent records.

Deleting or revoking a voice reference blocks later generation and removes derived generation records according to the active cleanup workflow.
