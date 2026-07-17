# Changelog

This file records changes that affect how MemWeave is installed, used, or maintained.

## [Unreleased]

## [0.2.0] - 2026-07-17

### Added

- Unsigned Windows x64 NSIS installer with bundled Electron, Next.js standalone frontend, and PyInstaller backend runtime.
- Full and per-profile unencrypted ZIP backups, conflict preview, merge/import-as-new behavior, and Settings/Dashboard controls.
- Optional local IndexTTS2 setup helper that requires existing model files and never downloads weights.
- Branded multi-size Windows application icon and packaged-resource verification.

### Changed

- Installed data, settings, logs, attachments, voice references, and generated audio now live under `%LOCALAPPDATA%\MemWeave`.
- Uninstall warns about local data deletion and removes the LocalAppData directory by default, including silent uninstall.
- Packaging prepares checksum-verified Electron locally and reuses that distribution during electron-builder runs.

### Fixed

- Included Next.js standalone runtime dependencies that electron-builder previously filtered from `extraResources`.
- Prevented silent uninstall from hanging on an interactive-only confirmation dialog.

## [0.1.0] - 2026-07-16

### Added

- Clean standalone MemWeave source repository.
- English and Simplified Chinese README files.
- PolyForm Noncommercial License 1.0.0.
- Contribution, security, conduct, architecture, startup, and CI documentation.
- Repository hygiene verification.

### Changed

- Development startup now uses a conventional Python virtual environment or PATH interpreter.
- Frontend readiness checks validate referenced Next.js static assets.
- Optional external AI features default to disabled until configured.
- Product metadata and runtime names use MemWeave.
- Mobile Chat height no longer forces the composer below the initial viewport.
- Deprecated Starlette 422 constants use the current name.
- Reworked the English and Chinese documentation to explain the project in direct, concrete language while keeping the technical and safety boundaries unchanged.
