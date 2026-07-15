import type { IngestResponse } from "@/lib/api";

import type { CopyDocumentKind } from "./config";

export function buildExportPayload(result: IngestResponse | null) {
  if (!result) {
    return null;
  }

  return {
    exported_at: new Date().toISOString(),
    raw_source: result.raw_source,
    persona_items: result.persona_items,
    persona_library_classification: result.persona_library_classification,
    pii_summary: result.pii_summary,
    routing_key: result.routing_key,
    diagnostics: result.diagnostics,
  };
}

export function buildMarkdownDocument(result: IngestResponse | null) {
  if (!result) {
    return "";
  }

  return [
    `# Ingest ${result.raw_source.id}`,
    "",
    "## Raw Source",
    `- Type: ${result.raw_source.source_type}`,
    `- Profile: ${result.raw_source.profile_id ?? "none"}`,
    `- Hash: ${result.raw_source.content_hash}`,
    "",
    "## Persona Items",
    ...(result.persona_items.length
      ? result.persona_items.map((item) => `- [${item.library_group}/${item.library_key}] ${item.signal}`)
      : ["- No persona items saved."]),
    "",
    "## Sanitized Content",
    result.sanitized_content,
  ].join("\n");
}

export function buildCopyDocument(result: IngestResponse | null, kind: CopyDocumentKind) {
  const payload = buildExportPayload(result);
  if (!result || !payload) {
    return "";
  }

  if (kind === "json") {
    return JSON.stringify(payload, null, 2);
  }
  if (kind === "markdown") {
    return buildMarkdownDocument(result);
  }
  if (kind === "prompt") {
    return result.persona_items.map((item) => item.prompt_snippet).filter(Boolean).join("\n");
  }
  return JSON.stringify(result.diagnostics, null, 2);
}

export async function copyText(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

export function downloadSkillExport(result: IngestResponse | null) {
  if (!result) {
    return;
  }

  const payload = buildExportPayload(result);
  if (!payload) {
    return;
  }

  const safeName = `persona-ingest-${result.raw_source.id}`.slice(0, 80);
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${safeName}-${timestamp}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
