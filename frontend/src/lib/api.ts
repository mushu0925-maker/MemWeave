export type SourceType =
  | "text"
  | "file"
  | "interview"
  | "extension"
  | "image"
  | "audio"
  | "book"
  | "manual"
  | "manual_override"
  | "chat";

export type IngestRequest = {
  source_type: SourceType;
  raw_content: string;
  metadata: Record<string, string | number | boolean | null>;
  profile_id?: string | null;
};

export type PersonaLibraryClassificationItem = {
  library_key: string;
  subject_scope: "target_person" | "source_author" | "other_person" | "relationship_dynamic" | "unknown";
  write_target:
    | "target_profile"
    | "narrator_profile"
    | "relationship_context"
    | "boundary_only"
    | "rejected_until_confirmed";
  signal: string;
  evidence_quote: string;
  evidence_relation: "direct_quote" | "close_paraphrase" | "semantic_inference";
  confidence: number;
  stability: "single_observation" | "candidate" | "stable" | "conflict" | "unknown";
  usage: "fact_only" | "style_only" | "judgment" | "scenario_rule" | "boundary_rule" | "retrieval_hint" | "do_not_use";
  risk: "none" | "low_sample" | "unsupported_fact" | "sensitive" | "safety_boundary" | "conflict" | "over_intimacy" | "impersonation";
  prompt_snippet: string;
  tags: string[];
  time_scope: string | null;
  priority: "ai_classified";
};

export type PersonaLibraryRejectedItem = {
  text_or_claim: string;
  reason: "irrelevant" | "too_vague" | "unsupported" | "unsafe" | "duplicate" | "needs_user_confirmation";
  note: string;
};

export type PersonaLibraryConflict = {
  library_key: string;
  conflict_summary: string;
  evidence_quotes: string[];
  resolution: "lower_confidence" | "split_by_time" | "needs_user_confirmation" | "ignore_weak_claim";
};

export type PersonaLibraryClassificationResult = {
  source_summary: string;
  source_period: string | null;
  dominant_categories: string[];
  items: PersonaLibraryClassificationItem[];
  rejected_items: PersonaLibraryRejectedItem[];
  conflicts: PersonaLibraryConflict[];
  notes: string[];
};

export type LibraryGroup = "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H" | "I" | "J" | "K" | "L" | "M";
export type PersonaItemStatus = "active" | "candidate" | "hidden" | "forgotten" | "rejected_until_confirmed" | "deleted";
export type ConfirmationOption = "keep" | "correct" | "downrank" | "hide" | "forget";
export type UncertainRiskType =
  | "unclear"
  | "low_confidence"
  | "conflict"
  | "negative_memory"
  | "sensitive"
  | "unsupported_fact";
export type UncertainItemStatus = "open" | "resolved" | "forgotten" | "hidden";
export type QuestionTargetReason = "missing" | "low_confidence" | "conflict" | "needs_example" | "needs_boundary";
export type QuestionTargetStatus = "open" | "answered" | "dismissed" | "resolved";
export type SegmentTargetPerson = "target_person" | "user" | "other" | "unknown";
export type SegmentAttributionStatus = "pending" | "confirmed" | "rejected" | "needs_review";

export type RawSourceSchema = {
  id: string;
  profile_id: string | null;
  source_type: SourceType;
  original_text: string;
  extracted_text: string;
  file_path: string | null;
  file_name: string | null;
  mime_type: string | null;
  content_hash: string;
  pii_masked_text: string;
  metadata: Record<string, unknown>;
  created_at: string;
  deleted_at: string | null;
};

export type SourceSegmentSchema = {
  id: string;
  raw_source_id: string;
  profile_id: string | null;
  source_type: SourceType;
  segment_index: number;
  start_char: number | null;
  end_char: number | null;
  start_seconds: number | null;
  end_seconds: number | null;
  text_excerpt: string;
  target_person: SegmentTargetPerson;
  attribution_status: SegmentAttributionStatus;
  consent_confirmed: boolean;
  consent_note: string;
  permitted_uses: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type SourceSegmentUpdate = {
  target_person?: SegmentTargetPerson;
  attribution_status?: SegmentAttributionStatus;
  consent_confirmed?: boolean;
  consent_note?: string | null;
  permitted_uses?: string[];
  metadata?: Record<string, unknown>;
};

export type SourceSegmentBackfillResponse = {
  profile_id: string | null;
  include_deleted: boolean;
  raw_source_count: number;
  raw_sources_missing_segment_before: number;
  raw_sources_with_segment_after: number;
  source_segments_created: number;
  extracted_segments_created: number;
  pending_segment_count: number;
  backfilled_raw_source_ids: string[];
};

export type ExtractedSegmentSchema = {
  id: string;
  source_segment_id: string;
  raw_source_id: string;
  profile_id: string | null;
  extraction_type: string;
  extracted_text: string;
  confidence: number;
  model_name: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type PersonaItemSchema = {
  id: string;
  profile_id: string;
  source_id: string | null;
  library_group: LibraryGroup;
  library_key: string;
  signal: string;
  evidence_quote: string;
  evidence_time_range: string | null;
  confidence: number;
  stability: string;
  subject_scope: string;
  write_target: string;
  risk: string;
  prompt_snippet: string;
  extraction_method: string;
  model_name: string | null;
  status: PersonaItemStatus;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type UncertainItemSchema = {
  id: string;
  profile_id: string;
  source_id: string | null;
  persona_item_id: string | null;
  library_group: LibraryGroup;
  library_key: string;
  claim: string;
  why_uncertain: string;
  risk_type: UncertainRiskType;
  suggested_question: string;
  confirmation_options: ConfirmationOption[];
  confidence: number;
  status: UncertainItemStatus;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type QuestionTargetSchema = {
  id: string;
  profile_id: string;
  source_id: string | null;
  uncertain_item_id: string | null;
  target_group: LibraryGroup;
  target_library_key: string;
  reason: QuestionTargetReason;
  question: string;
  example_answer: string;
  priority: number;
  expected_evidence_type: string;
  status: QuestionTargetStatus;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type QuestionAnswerRequest = {
  answer_text: string;
  metadata?: Record<string, unknown>;
};

export type QuestionAnswerResponse = {
  raw_source: RawSourceSchema;
  persona_items: PersonaItemSchema[];
  question_target: QuestionTargetSchema;
  uncertain_item: UncertainItemSchema | null;
  persona_library_classification: PersonaLibraryClassificationResult | null;
  classification_succeeded: boolean;
  diagnostics: Record<string, unknown>;
};

export type UncertainItemActionRequest = {
  action: ConfirmationOption;
  corrected_claim?: string | null;
  note?: string | null;
  metadata?: Record<string, unknown>;
};

export type UncertainItemActionResponse = {
  uncertain_item: UncertainItemSchema;
  question_targets: QuestionTargetSchema[];
  action: ConfirmationOption;
  raw_source: RawSourceSchema | null;
  persona_items: PersonaItemSchema[];
  persona_library_classification: PersonaLibraryClassificationResult | null;
  classification_succeeded: boolean;
  diagnostics: Record<string, unknown>;
};

export type IngestResponse = {
  raw_source: RawSourceSchema;
  persona_items: PersonaItemSchema[];
  sanitized_content: string;
  pii_summary: Record<string, number>;
  routing_key: string;
  persona_library_classification: PersonaLibraryClassificationResult | null;
  diagnostics: IngestDiagnostics;
};

export type CoverageWarning = {
  type: string;
  library_group: LibraryGroup;
  category: string;
  label: string;
  expected_library_keys: string[];
  risk_type: string;
  suggested_question: string;
  confirmation_options: string[];
};

export type IngestDiagnostics = Record<string, unknown> & {
  coverage_warnings?: CoverageWarning[];
  persisted_uncertain_items?: number;
  persisted_question_targets?: number;
  uncertain_item_ids?: string[];
  question_target_ids?: string[];
  uncertainty_skipped_warnings?: string[];
  voice_feature_question_target_id?: string;
  voice_feature_target_group?: LibraryGroup;
  voice_feature_target_library_key?: string;
  voice_feature_safety?: string;
};

export type RelationshipType = "family" | "friend" | "partner" | "mentor" | "self" | "other";

export type ProfileSchema = {
  id: string;
  display_name: string;
  relationship: RelationshipType;
  description: string;
  boundaries: string[];
  created_at: string;
  updated_at: string;
};

export type ProfileDetailResponse = {
  profile: ProfileSchema;
  raw_source_count: number;
  persona_item_count: number;
  uncertain_item_count: number;
  question_target_count: number;
};

export type ProfileStage =
  | "empty"
  | "raw_only"
  | "library_ready"
  | "needs_confirmation"
  | "skill_saved"
  | "chat_ready"
  | "config_missing";

export type ProfileStatusResponse = {
  profile_id: string;
  stage: ProfileStage;
  stage_label: string;
  next_action: string;
  raw_source_count: number;
  persona_item_count: number;
  open_question_count: number;
  open_uncertain_count: number;
  skill_version_count: number;
  latest_skill_version_id: string | null;
  ai_configured: boolean;
  can_generate_skill: boolean;
  can_chat: boolean;
  warnings: string[];
};

export type ProfileCreateRequest = {
  display_name: string;
  relationship: RelationshipType;
  description?: string;
  boundaries?: string[];
};

export type ProfileUpdateRequest = {
  display_name?: string;
  relationship?: RelationshipType;
  description?: string;
  boundaries?: string[];
};

export type AIConfigResponse = {
  llm_api_key_configured: boolean;
  llm_api_key_preview: string | null;
  llm_base_url: string | null;
  llm_proxy_url: string | null;
  llm_model: string;
  chat_use_custom_config: boolean;
  chat_api_key_configured: boolean;
  chat_api_key_preview: string | null;
  chat_base_url: string | null;
  chat_model: string;
  chat_effective_base_url: string | null;
  chat_effective_model: string;
  chat_enabled: boolean;
  persona_use_custom_config: boolean;
  persona_api_key_configured: boolean;
  persona_api_key_preview: string | null;
  persona_base_url: string | null;
  persona_model: string;
  persona_effective_base_url: string | null;
  persona_effective_model: string;
  persona_enabled: boolean;
  translate_model: string;
  evolution_model: string;
  vision_use_custom_config: boolean;
  vision_api_key_configured: boolean;
  vision_api_key_preview: string | null;
  vision_base_url: string | null;
  vision_model: string;
  vision_effective_base_url: string | null;
  vision_effective_model: string;
  asr_use_custom_config: boolean;
  asr_api_key_configured: boolean;
  asr_api_key_preview: string | null;
  asr_base_url: string | null;
  asr_model: string;
  asr_effective_base_url: string | null;
  asr_effective_model: string;
  enable_ai_classification: boolean;
  enable_vision_ocr: boolean;
  enable_asr: boolean;
  llm_enabled: boolean;
  vision_enabled: boolean;
  asr_enabled: boolean;
};

export type AIConfigUpdateRequest = {
  llm_api_key?: string | null;
  llm_base_url?: string | null;
  llm_proxy_url?: string | null;
  llm_model?: string | null;
  chat_use_custom_config?: boolean;
  chat_api_key?: string | null;
  chat_base_url?: string | null;
  chat_model?: string | null;
  persona_use_custom_config?: boolean;
  persona_api_key?: string | null;
  persona_base_url?: string | null;
  persona_model?: string | null;
  translate_model?: string | null;
  evolution_model?: string | null;
  vision_use_custom_config?: boolean;
  vision_api_key?: string | null;
  vision_base_url?: string | null;
  vision_model?: string | null;
  asr_use_custom_config?: boolean;
  asr_api_key?: string | null;
  asr_base_url?: string | null;
  asr_model?: string | null;
  enable_ai_classification?: boolean;
  enable_vision_ocr?: boolean;
  enable_asr?: boolean;
};

export type AIModelOption = {
  id: string;
  label: string;
  note: string;
};

export type AIModelOptionsResponse = {
  text_models: AIModelOption[];
  vision_models: AIModelOption[];
  asr_models: AIModelOption[];
};

export type AIModelDiscoveryFeature = "global" | "chat" | "classification" | "vision" | "asr";

export type AIModelDiscoveryResponse = {
  feature: AIModelDiscoveryFeature;
  status: "available" | "empty" | "not_configured" | "unavailable";
  source: "provider" | "none";
  models: AIModelOption[];
  message: string;
};

export type AIConnectionTestResponse = {
  ok: boolean;
  status: string;
  provider: string;
  model: string;
  message: string;
  error: string | null;
};

export type ChatRequest = {
  message: string;
  chat_mode?: ChatMode;
  use_model?: boolean;
  save_record?: boolean;
  skill_version_id?: string | null;
};

export type ChatMode = "direct" | "third_person";

export type ChatRecord = {
  id: string;
  profile_id: string;
  chat_mode: ChatMode;
  user_message: string;
  assistant_message: string;
  model_call_status: "success" | "failed" | "skipped" | "blocked" | "local";
  model_call_reason: string;
  provider: string;
  model_name: string | null;
  used_persona_item_ids: string[];
  used_raw_source_ids: string[];
  created_at: string;
};

export type ChatRuntimeStatus = {
  generated_skill_available: boolean;
  generated_skill_used: boolean;
  runtime_pack_in_prompt: boolean;
  skill_version: string | null;
  skill_version_id: string | null;
  skill_version_title: string | null;
  skill_generated_at: string | null;
  evidence_unit_count: number;
  runtime_slice_unit_count: number;
  audit_count: number;
  question_backlog_count: number;
  reason: string;
};

export type ChatResponse = {
  record: ChatRecord;
  context_summary: string;
  runtime_status: ChatRuntimeStatus;
  candidate_evidence: {
    created?: boolean;
    reason?: string | null;
    raw_source_id?: string | null;
    uncertain_item_id?: string | null;
    question_target_id?: string | null;
  };
};

export type ChatClearResponse = {
  profile_id: string;
  deleted_count: number;
};

export type VoiceGenerationStatusResponse = {
  enabled: boolean;
  provider: string;
  configured: boolean;
  base_url: string | null;
  reference_dir: string;
  output_dir: string;
  ffmpeg_configured: boolean;
  ffmpeg_path: string;
  ffmpeg_available: boolean;
  ffmpeg_error: string;
  video_reference_supported: boolean;
  safety: string;
};

export type VoiceReferenceUploadResponse = {
  raw_source_id: string;
  profile_id: string;
  file_name: string;
  mime_type: string;
  file_path: string;
  size_bytes: number;
  consent_confirmed: boolean;
  ai_generated_notice_required: boolean;
  voice_reference_kind: "audio" | "video";
  tts_reference_ready: boolean;
  audio_extraction_status: string;
  audio_extraction_error: string;
  source_segment_id: string | null;
  segment_target_person: SegmentTargetPerson;
  segment_attribution_status: SegmentAttributionStatus;
  voice_generation_ready: boolean;
  voice_generation_block_reason: string;
  message: string;
};

export type VoiceGenerationRequest = {
  reply_text: string;
  reference_raw_source_id: string;
  chat_record_id?: string | null;
  consent_confirmed: boolean;
  model?: string;
  emotion?: string | null;
  generation_notes?: string;
};

export type VoiceGenerationRecord = {
  id: string;
  profile_id: string;
  reference_raw_source_id: string;
  chat_record_id: string | null;
  reply_text: string;
  model: string;
  provider: string;
  status: "success" | "failed" | "blocked" | "skipped";
  consent_confirmed: boolean;
  ai_generated: boolean;
  output_file_path: string | null;
  output_mime_type: string | null;
  duration_seconds: number | null;
  error: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type VoiceGenerationResponse = {
  record: VoiceGenerationRecord;
  audio_url: string | null;
  message: string;
};

export type VoiceGenerationListResponse = {
  records: VoiceGenerationRecord[];
};

export type SkillEvidenceBucket = "core" | "supporting" | "caution" | "audit" | "excluded";

export type SkillUsageMatrix = {
  can_retrieve: boolean;
  can_generate_style: boolean;
  can_state_as_fact: boolean;
  can_quote: boolean;
  can_simulate: boolean;
  needs_caution: boolean;
  needs_question: boolean;
  audit_only: boolean;
};

export type SkillEvidenceUnit = {
  unit_id: string;
  profile_id: string;
  source_id: string | null;
  persona_item_id: string;
  library_group: LibraryGroup;
  library_key: string;
  claim_text: string;
  evidence_quote: string;
  evidence_type: string;
  context_signature: Record<string, string>;
  source_role: string;
  subject_scope: string;
  time_range: string | null;
  source_deleted: boolean;
  user_policy: string;
  risk: string;
  status: string;
  confidence_parts: Record<string, number>;
  ranking_score: number;
  bucket: SkillEvidenceBucket;
  cap_rule: string;
  cap_reason: string;
  usage: SkillUsageMatrix;
  score_reason: string[];
};

export type SkillLibrarySection = {
  library_group: LibraryGroup;
  core: SkillEvidenceUnit[];
  supporting: SkillEvidenceUnit[];
  caution: SkillEvidenceUnit[];
};

export type SkillQuestionBacklogItem = {
  question_target_id: string;
  source_id: string | null;
  target_group: LibraryGroup;
  target_library_key: string;
  reason: string;
  question: string;
  priority: number;
  expected_evidence_type: string;
};

export type SkillAuditEntry = {
  subject_type: string;
  subject_id: string;
  reason: string;
  detail: string;
  source_id: string | null;
  metadata: Record<string, unknown>;
};

export type SkillGenerationResponse = {
  profile_id: string;
  generated_at: string;
  version: string;
  skill_markdown: string;
  libraries: Record<string, SkillLibrarySection>;
  evidence_units: SkillEvidenceUnit[];
  caution_report: SkillEvidenceUnit[];
  question_backlog: SkillQuestionBacklogItem[];
  audit_report: SkillAuditEntry[];
  diagnostics: Record<string, unknown>;
};

export type SkillVersion = {
  id: string;
  profile_id: string;
  title: string;
  notes: string;
  source_generation_version: string;
  skill_markdown: string;
  skill_json: SkillGenerationResponse;
  evidence_unit_count: number;
  audit_count: number;
  question_backlog_count: number;
  created_at: string;
};

export type SkillVersionListResponse = {
  versions: SkillVersion[];
};

export type SkillVersionCreateRequest = {
  title?: string | null;
  notes?: string | null;
  skill: SkillGenerationResponse;
};

export type SystemCheckStatus = "pass" | "warning" | "fail" | "blocked";

export type SystemSelfCheckItem = {
  key: string;
  label: string;
  status: SystemCheckStatus;
  summary: string;
  detail: string;
  action: string;
  metadata: Record<string, unknown>;
};

export type SystemSelfCheckResponse = {
  generated_at: string;
  app_name: string;
  environment: string;
  api_prefix: string;
  overall_status: SystemCheckStatus;
  checks: SystemSelfCheckItem[];
  required_routes: Record<string, boolean>;
  summary: Record<string, number>;
};

export type AcceptanceCheckStatus = "pass" | "warning" | "fail" | "blocked" | "skipped";

export type AcceptanceRunRequest = {
  profile_id?: string | null;
  create_isolated_profile?: boolean;
  use_model_for_chat?: boolean;
  raw_content?: string | null;
  updated_by?: string;
};

export type AcceptanceCheckResult = {
  key: string;
  name: string;
  status: AcceptanceCheckStatus;
  module: string;
  record_ids: string[];
  reason: string;
  expected: string;
  actual: string;
  evidence: Record<string, unknown>;
  action_hint: string;
  suggested_action: string;
};

export type AcceptanceRunResponse = {
  run_id: string;
  started_at: string;
  finished_at: string;
  feature_policy: Record<string, unknown>;
  overall_status: "pass" | "warning" | "fail" | "blocked";
  profile_id: string | null;
  created_profile_id: string | null;
  algorithm_key: string;
  strictness: string;
  checks: AcceptanceCheckResult[];
  summary: Record<string, number>;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const API_UNAVAILABLE_MESSAGE = `Cannot connect to backend API (${API_BASE_URL}).`;

function absoluteApiUrl(path: string | null): string | null {
  if (!path) {
    return null;
  }
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function errorMessageFromResponse(response: Response): Promise<string> {
  const errorText = await response.text();
  if (!errorText) {
    return `Request failed with status ${response.status}`;
  }

  try {
    const parsed = JSON.parse(errorText) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
    if (parsed.detail && typeof parsed.detail === "object" && !Array.isArray(parsed.detail)) {
      const detail = parsed.detail as {
        message?: unknown;
        raw_source_id?: unknown;
        model_call_status?: unknown;
        model_call_reason?: unknown;
        model_name?: unknown;
        notes?: unknown;
      };
      const lines = [
        typeof detail.message === "string" ? detail.message : "",
        typeof detail.raw_source_id === "string" ? `raw_source_id: ${detail.raw_source_id}` : "",
        typeof detail.model_call_status === "string" ? `model: ${detail.model_call_status}` : "",
        typeof detail.model_name === "string" ? `model_name: ${detail.model_name}` : "",
        typeof detail.model_call_reason === "string" && detail.model_call_reason ? `reason: ${detail.model_call_reason}` : "",
      ];
      if (Array.isArray(detail.notes)) {
        lines.push(...detail.notes.filter((note): note is string => typeof note === "string"));
      }
      const message = lines.filter(Boolean).join("\n");
      if (message) {
        return message;
      }
    }
    if (Array.isArray(parsed.detail)) {
      return parsed.detail
        .map((item) => {
          if (item && typeof item === "object") {
            const detail = item as { loc?: unknown[]; msg?: unknown };
            const field = Array.isArray(detail.loc) ? detail.loc.slice(1).join(".") : "";
            const message = typeof detail.msg === "string" ? detail.msg : JSON.stringify(item);
            return field ? `${field}: ${message}` : message;
          }
          return JSON.stringify(item);
        })
        .join("\n");
    }
  } catch {
    return errorText;
  }

  return errorText;
}

async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(API_UNAVAILABLE_MESSAGE);
    }
    throw error;
  }
}

export async function ingestSkill(payload: IngestRequest): Promise<IngestResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/ingest`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<IngestResponse>;
}

export async function ingestFile(upload: File, notes: string, profileId?: string | null): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append("upload", upload);
  formData.append("notes", notes);
  if (profileId) {
    formData.append("profile_id", profileId);
  }

  const response = await apiFetch(`${API_BASE_URL}/api/v1/ingest/file`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<IngestResponse>;
}

export async function listProfiles(): Promise<ProfileSchema[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/profiles`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<ProfileSchema[]>;
}

export async function createProfile(payload: ProfileCreateRequest): Promise<ProfileSchema> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/profiles`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<ProfileSchema>;
}

export async function updateProfile(profileId: string, payload: ProfileUpdateRequest): Promise<ProfileSchema> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/profiles/${profileId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<ProfileSchema>;
}

export async function deleteProfile(profileId: string): Promise<ProfileSchema> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/profiles/${profileId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<ProfileSchema>;
}

export async function getProfile(profileId: string): Promise<ProfileDetailResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/profiles/${profileId}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<ProfileDetailResponse>;
}

export async function getProfileStatus(profileId: string): Promise<ProfileStatusResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/profiles/${profileId}/status`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<ProfileStatusResponse>;
}

export async function listRawSources(
  profileId?: string | null,
  options: { includeDeleted?: boolean; deletedOnly?: boolean } = {},
): Promise<RawSourceSchema[]> {
  const params = new URLSearchParams();
  if (profileId) {
    params.set("profile_id", profileId);
  }
  if (options.includeDeleted) {
    params.set("include_deleted", "true");
  }
  if (options.deletedOnly) {
    params.set("deleted_only", "true");
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await apiFetch(`${API_BASE_URL}/api/v1/raw-sources${query}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<RawSourceSchema[]>;
}

export async function listSourceSegments(
  options: { profileId?: string | null; rawSourceId?: string | null; ensureMissing?: boolean } = {},
): Promise<SourceSegmentSchema[]> {
  const params = new URLSearchParams();
  if (options.profileId) {
    params.set("profile_id", options.profileId);
  }
  if (options.rawSourceId) {
    params.set("raw_source_id", options.rawSourceId);
  }
  if (options.ensureMissing) {
    params.set("ensure_missing", "true");
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await apiFetch(`${API_BASE_URL}/api/v1/source-segments${query}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<SourceSegmentSchema[]>;
}

export async function updateSourceSegment(
  segmentId: string,
  payload: SourceSegmentUpdate,
): Promise<SourceSegmentSchema> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/source-segments/${segmentId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<SourceSegmentSchema>;
}

export async function ensureRawSourceSegments(rawSourceId: string): Promise<SourceSegmentSchema[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/source-segments/raw-sources/${rawSourceId}/ensure`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<SourceSegmentSchema[]>;
}

export async function backfillSourceSegments(
  options: { profileId?: string | null; includeDeleted?: boolean } = {},
): Promise<SourceSegmentBackfillResponse> {
  const params = new URLSearchParams();
  if (options.profileId) {
    params.set("profile_id", options.profileId);
  }
  if (options.includeDeleted) {
    params.set("include_deleted", "true");
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await apiFetch(`${API_BASE_URL}/api/v1/source-segments/backfill${query}`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<SourceSegmentBackfillResponse>;
}

export async function listPersonaItems(
  profileId?: string | null,
  options: { deletedOnly?: boolean } = {},
): Promise<PersonaItemSchema[]> {
  const params = new URLSearchParams();
  if (profileId) {
    params.set("profile_id", profileId);
  }
  if (options.deletedOnly) {
    params.set("deleted_only", "true");
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await apiFetch(`${API_BASE_URL}/api/v1/persona-items${query}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<PersonaItemSchema[]>;
}

export async function deleteRawSource(sourceId: string): Promise<RawSourceSchema> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/raw-sources/${sourceId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<RawSourceSchema>;
}

export async function restoreRawSource(sourceId: string): Promise<RawSourceSchema> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/raw-sources/${sourceId}/restore`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<RawSourceSchema>;
}

export async function purgeRawSource(sourceId: string): Promise<RawSourceSchema> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/raw-sources/${sourceId}/purge`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<RawSourceSchema>;
}

export async function deletePersonaItem(itemId: string): Promise<PersonaItemSchema> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/persona-items/${itemId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<PersonaItemSchema>;
}

export async function restorePersonaItem(itemId: string): Promise<PersonaItemSchema> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/persona-items/${itemId}/restore`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<PersonaItemSchema>;
}

export async function purgePersonaItem(itemId: string): Promise<PersonaItemSchema> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/persona-items/${itemId}/purge`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<PersonaItemSchema>;
}

export async function listUncertainItems(
  profileId?: string | null,
  includeClosed = false,
): Promise<UncertainItemSchema[]> {
  const params = new URLSearchParams();
  if (profileId) {
    params.set("profile_id", profileId);
  }
  if (includeClosed) {
    params.set("include_closed", "true");
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await apiFetch(`${API_BASE_URL}/api/v1/uncertain-items${query}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<UncertainItemSchema[]>;
}

export async function listQuestionTargets(
  profileId?: string | null,
  includeClosed = false,
): Promise<QuestionTargetSchema[]> {
  const params = new URLSearchParams();
  if (profileId) {
    params.set("profile_id", profileId);
  }
  if (includeClosed) {
    params.set("include_closed", "true");
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await apiFetch(`${API_BASE_URL}/api/v1/question-targets${query}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<QuestionTargetSchema[]>;
}

export async function answerQuestionTarget(
  questionId: string,
  payload: QuestionAnswerRequest,
): Promise<QuestionAnswerResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/question-targets/${questionId}/answer`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<QuestionAnswerResponse>;
}

export async function actOnUncertainItem(
  itemId: string,
  payload: UncertainItemActionRequest,
): Promise<UncertainItemActionResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/uncertain-items/${itemId}/action`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<UncertainItemActionResponse>;
}

export async function reextractRawSource(sourceId: string): Promise<IngestResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/raw-sources/${sourceId}/reextract`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<IngestResponse>;
}

export async function listChatMessages(profileId: string): Promise<ChatRecord[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/chat/profiles/${profileId}/messages`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<ChatRecord[]>;
}

export async function clearChatMessages(profileId: string): Promise<ChatClearResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/chat/profiles/${profileId}/messages`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<ChatClearResponse>;
}

export async function chatWithProfile(profileId: string, payload: ChatRequest): Promise<ChatResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/chat/profiles/${profileId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<ChatResponse>;
}

export async function getVoiceGenerationStatus(): Promise<VoiceGenerationStatusResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/voice/status`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<VoiceGenerationStatusResponse>;
}

export async function uploadVoiceReference(
  profileId: string,
  upload: File,
  consentConfirmed: boolean,
  consentNote: string,
): Promise<VoiceReferenceUploadResponse> {
  const formData = new FormData();
  formData.append("upload", upload);
  formData.append("consent_confirmed", consentConfirmed ? "true" : "false");
  formData.append("consent_note", consentNote);

  const response = await apiFetch(`${API_BASE_URL}/api/v1/voice/profiles/${profileId}/references`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<VoiceReferenceUploadResponse>;
}

export async function extractVoiceReferenceAudio(
  profileId: string,
  rawSourceId: string,
): Promise<VoiceReferenceUploadResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/voice/profiles/${profileId}/references/${rawSourceId}/extract-audio`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<VoiceReferenceUploadResponse>;
}

export async function generateAuthorizedVoice(
  profileId: string,
  payload: VoiceGenerationRequest,
): Promise<VoiceGenerationResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/voice/profiles/${profileId}/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  const result = (await response.json()) as VoiceGenerationResponse;
  return {
    ...result,
    audio_url: absoluteApiUrl(result.audio_url),
  };
}

export async function listVoiceGenerations(profileId: string): Promise<VoiceGenerationRecord[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/voice/profiles/${profileId}/generations`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  const result = (await response.json()) as VoiceGenerationListResponse;
  return result.records;
}

export function voiceGenerationAudioUrl(recordId: string): string {
  return absoluteApiUrl(`/api/v1/voice/generations/${recordId}/audio`) ?? "";
}

export async function generateSkill(profileId: string, includeAuditUnits = true): Promise<SkillGenerationResponse> {
  const params = new URLSearchParams({
    profile_id: profileId,
    include_audit_units: includeAuditUnits ? "true" : "false",
  });
  const response = await apiFetch(`${API_BASE_URL}/api/v1/skills/generate?${params.toString()}`, {
    method: "POST",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<SkillGenerationResponse>;
}

export async function listSkillVersions(profileId: string): Promise<SkillVersion[]> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/skills/profiles/${profileId}/versions`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  const payload = (await response.json()) as SkillVersionListResponse;
  return payload.versions;
}

export async function saveSkillVersion(profileId: string, payload: SkillVersionCreateRequest): Promise<SkillVersion> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/skills/profiles/${profileId}/versions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<SkillVersion>;
}

export async function deleteSkillVersion(profileId: string, versionId: string): Promise<SkillVersion> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/skills/profiles/${profileId}/versions/${versionId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<SkillVersion>;
}

export async function getAIConfig(): Promise<AIConfigResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/config/ai`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<AIConfigResponse>;
}

export async function updateAIConfig(payload: AIConfigUpdateRequest): Promise<AIConfigResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/config/ai`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<AIConfigResponse>;
}

export async function testAIConnection(): Promise<AIConnectionTestResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/config/ai/test`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<AIConnectionTestResponse>;
}

export async function getAIModelOptions(): Promise<AIModelOptionsResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/config/ai/models`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<AIModelOptionsResponse>;
}

export async function discoverAIModels(feature: AIModelDiscoveryFeature): Promise<AIModelDiscoveryResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/config/ai/models/discover?feature=${encodeURIComponent(feature)}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<AIModelDiscoveryResponse>;
}

export async function getSystemSelfCheck(): Promise<SystemSelfCheckResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/system/self-check`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<SystemSelfCheckResponse>;
}

export async function runAcceptanceE2E(payload: AcceptanceRunRequest = {}): Promise<AcceptanceRunResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/acceptance/e2e/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }

  return response.json() as Promise<AcceptanceRunResponse>;
}

export type BackupProfilePreview = {
  id: string;
  display_name: string;
  relationship: string;
  deleted: boolean;
  raw_source_count: number;
  persona_item_count: number;
  chat_record_count: number;
  voice_generation_count: number;
  conflicts_with_local: boolean;
};

export type BackupImportPreview = {
  import_token: string;
  scope: "full" | "profile";
  created_at: string;
  profiles: BackupProfilePreview[];
  conflict_profile_ids: string[];
  document_count: number;
  attachment_count: number;
  attachment_bytes: number;
  warnings: string[];
};

export type BackupImportRequest = {
  import_token: string;
  profile_conflict_mode: "merge" | "import_as_new";
  global_data_mode?: "keep_existing" | "merge";
};

export type BackupImportResponse = {
  scope: "full" | "profile";
  imported_profile_ids: string[];
  remapped_profile_ids: Record<string, string>;
  imported_document_counts: Record<string, number>;
  imported_attachment_count: number;
  skipped_global_documents: string[];
  warnings: string[];
};

async function downloadBackup(path: string): Promise<Blob> {
  const response = await apiFetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }
  return response.blob();
}

export function downloadFullBackup(): Promise<Blob> {
  return downloadBackup("/api/v1/backups/export");
}

export function downloadProfileBackup(profileId: string): Promise<Blob> {
  return downloadBackup(`/api/v1/backups/profiles/${encodeURIComponent(profileId)}/export`);
}

export async function inspectBackup(upload: File): Promise<BackupImportPreview> {
  const formData = new FormData();
  formData.append("upload", upload);
  const response = await apiFetch(`${API_BASE_URL}/api/v1/backups/inspect`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }
  return response.json() as Promise<BackupImportPreview>;
}

export async function importBackup(payload: BackupImportRequest): Promise<BackupImportResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/v1/backups/import`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await errorMessageFromResponse(response));
  }
  return response.json() as Promise<BackupImportResponse>;
}
