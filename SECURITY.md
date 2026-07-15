# Security Policy

## Supported Version

Security fixes target the latest version on the default branch.

## Reporting a Vulnerability

Do not publish sensitive vulnerability details in a public issue. Use GitHub private vulnerability reporting when enabled, or contact the repository maintainer through a private channel listed on the maintainer's profile.

Include the affected version, reproduction steps, impact, and any suggested mitigation. Do not include real API keys or personal memory material.

## Deployment Boundary

MemWeave is a local single-user MVP. The FastAPI backend does not currently enforce production authentication, authorization, tenant isolation, or deployment-layer upload limits. Do not expose it directly to the public internet.

For any network deployment, add at minimum:

- authenticated users and per-user data isolation;
- TLS and trusted reverse-proxy configuration;
- request and upload size limits at the ASGI/proxy layer;
- secret management outside the repository;
- a production database, backups, retention rules, and audit logging;
- origin restrictions appropriate for the deployment.

## Sensitive Data

Raw personal material, extracted text, persona items, chat history, voice references, generated audio, and API credentials may all be sensitive. Store them locally by default, minimize retention, and honor correction, hiding, forgetting, and deletion decisions.

Voice imitation requires explicit authorization. Voice references and generated output must never be committed to this repository.
