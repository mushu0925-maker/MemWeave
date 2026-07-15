"use client";

import Link from "next/link";
import {
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Bot,
  Check,
  Database,
  Headphones,
  Loader2,
  MessageCircle,
  Mic2,
  PanelRight,
  RefreshCw,
  Send,
  Settings2,
  Trash2,
  Upload,
  UserRound,
  Volume2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  chatWithProfile,
  clearChatMessages,
  deleteSkillVersion,
  ensureRawSourceSegments,
  extractVoiceReferenceAudio,
  generateAuthorizedVoice,
  getProfileStatus,
  getVoiceGenerationStatus,
  listChatMessages,
  listPersonaItems,
  listProfiles,
  listRawSources,
  listSourceSegments,
  listSkillVersions,
  listVoiceGenerations,
  uploadVoiceReference,
  updateSourceSegment,
  voiceGenerationAudioUrl,
  type ChatMode,
  type ChatRecord,
  type ChatRuntimeStatus,
  type PersonaItemSchema,
  type ProfileSchema,
  type ProfileStatusResponse,
  type RawSourceSchema,
  type SourceSegmentSchema,
  type SkillVersion,
  type VoiceGenerationRecord,
  type VoiceGenerationStatusResponse,
  type VoiceReferenceUploadResponse,
} from "@/lib/api";
import { notifyWorkspaceStatusChanged, readActiveProfileId, setActiveProfileId } from "@/lib/workspace-state";

type InspectorTab = "voice" | "runtime";

type VoiceReferenceItem = {
  raw_source_id: string;
  profile_id: string;
  file_name: string;
  mime_type: string;
  file_path: string;
  consent_confirmed: boolean;
  ai_generated_notice_required: boolean;
  voice_reference_kind: "audio" | "video";
  tts_reference_ready: boolean;
  audio_extraction_status: string;
  audio_extraction_error: string;
  source_segment_id: string | null;
  segment_target_person: SourceSegmentSchema["target_person"];
  segment_attribution_status: SourceSegmentSchema["attribution_status"];
  voice_generation_ready: boolean;
  voice_generation_block_reason: string;
  message: string;
  created_at: string;
  consent_note: string;
};

const PREVIEW_TEXT = "你好，这是当前授权参考声音的声色预览。";

const chatModeOptions: { value: ChatMode; label: string; description: string }[] = [
  {
    value: "direct",
    label: "和 TA 聊",
    description: "按已确认的记忆依据做边界内回应。",
  },
  {
    value: "third_person",
    label: "聊聊 TA",
    description: "不扮演 TA，陪你整理回忆。",
  },
];

function formatDate(value: string | null | undefined) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function metadataText(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key];
  return typeof value === "string" ? value.trim() : "";
}

function metadataBool(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key];
  return value === true || value === "true";
}

function segmentForSource(source: RawSourceSchema, segments: SourceSegmentSchema[]) {
  return (
    segments.find((segment) => segment.raw_source_id === source.id && segment.metadata.purpose === "voice_reference") ??
    segments.find((segment) => segment.raw_source_id === source.id) ??
    null
  );
}

function segmentVoiceBlockReason(segment: SourceSegmentSchema | null) {
  if (!segment) {
    return "需要先生成并确认声音片段归属";
  }
  if (segment.target_person !== "target_person") {
    return "需要确认这段声音属于当前人物";
  }
  if (segment.attribution_status !== "confirmed") {
    return "需要确认片段归属";
  }
  if (!segment.consent_confirmed) {
    return "需要确认片段授权";
  }
  if (!segment.permitted_uses.includes("voice_generation") && !segment.permitted_uses.includes("voice_reference")) {
    return "片段未允许用于声音生成";
  }
  return "";
}

function voiceReferenceFromRawSource(source: RawSourceSchema, segments: SourceSegmentSchema[]): VoiceReferenceItem | null {
  if (source.deleted_at || !metadataBool(source.metadata, "voice_reference")) {
    return null;
  }

  const segment = segmentForSource(source, segments);
  const kind = metadataText(source.metadata, "voice_reference_kind") === "video" ? "video" : "audio";
  const extractionStatus = metadataText(source.metadata, "voice_reference_audio_extraction_status");
  const ttsPath = metadataText(source.metadata, "voice_reference_tts_file_path");
  const ready = kind === "audio" || extractionStatus === "extracted";
  const segmentBlockReason = segmentVoiceBlockReason(segment);

  return {
    raw_source_id: source.id,
    profile_id: source.profile_id ?? "",
    file_name:
      metadataText(source.metadata, "voice_reference_original_filename") ||
      source.file_name ||
      "voice-reference",
    mime_type: metadataText(source.metadata, "voice_reference_tts_mime_type") || source.mime_type || "",
    file_path: ttsPath || metadataText(source.metadata, "voice_reference_original_file_path") || source.file_path || "",
    consent_confirmed: metadataBool(source.metadata, "voice_reference_consent_confirmed"),
    ai_generated_notice_required: metadataBool(source.metadata, "voice_reference_ai_generated_notice_required"),
    voice_reference_kind: kind,
    tts_reference_ready: ready,
    audio_extraction_status: extractionStatus || (kind === "audio" ? "not_required" : "pending"),
    audio_extraction_error: metadataText(source.metadata, "voice_reference_audio_extraction_error"),
    source_segment_id: segment?.id ?? null,
    segment_target_person: segment?.target_person ?? "unknown",
    segment_attribution_status: segment?.attribution_status ?? "pending",
    voice_generation_ready: ready && !segmentBlockReason,
    voice_generation_block_reason: !ready ? "" : segmentBlockReason,
    message: "Saved authorized voice reference.",
    created_at: source.created_at,
    consent_note: metadataText(source.metadata, "voice_reference_consent_note"),
  };
}

function voiceReferenceFromUpload(response: VoiceReferenceUploadResponse): VoiceReferenceItem {
  return {
    ...response,
    created_at: new Date().toISOString(),
    consent_note: "",
  };
}

function defaultVoiceReferenceKey(profileId: string) {
  return `voice-reference-default:${profileId}`;
}

function runtimeSummary(runtimeStatus: ChatRuntimeStatus | null) {
  if (!runtimeStatus) {
    return "发送后显示本次回复依据。";
  }
  if (runtimeStatus.generated_skill_used) {
    const version = runtimeStatus.skill_version_title ? ` / ${runtimeStatus.skill_version_title}` : "";
    return `本次使用 ${runtimeStatus.runtime_slice_unit_count}/${runtimeStatus.evidence_unit_count} 条记忆依据${version}`;
  }
  if (runtimeStatus.generated_skill_available) {
    return `已有可用依据，但本次未接入模型 / ${runtimeStatus.reason || "未使用"}`;
  }
  return `本次没有可用回复依据 / ${runtimeStatus.reason || "生成失败"}`;
}

function modeLabel(mode: ChatMode | undefined) {
  return mode === "third_person" ? "聊聊 TA" : "和 TA 聊";
}

function voiceReferenceStatusLabel(reference: VoiceReferenceItem) {
  if (reference.tts_reference_ready && reference.voice_generation_ready) {
    return "可用";
  }
  if (reference.tts_reference_ready && !reference.voice_generation_ready) {
    return "待确认片段";
  }
  if (reference.voice_reference_kind === "video") {
    return reference.audio_extraction_status || "需抽取音频";
  }
  return "不可用";
}

function generationStatusLabel(status: string) {
  if (status === "success") {
    return "成功";
  }
  if (status === "failed" || status === "error") {
    return "失败";
  }
  if (status === "pending" || status === "running") {
    return "生成中";
  }
  return status;
}

function voiceUseBlockReason(
  status: VoiceGenerationStatusResponse | null,
  reference: VoiceReferenceItem | null,
) {
  if (!status) {
    return "正在读取声音服务状态";
  }
  if (!status.enabled) {
    return "IndexTTS2 未启用";
  }
  if (!status.configured) {
    return "IndexTTS2 未配置";
  }
  if (!reference) {
    return "请选择一个参考声线";
  }
  if (!reference.consent_confirmed) {
    return "参考声线缺少授权确认";
  }
  if (!reference.tts_reference_ready) {
    return reference.voice_reference_kind === "video" ? "视频参考还没有抽出可用音频" : "参考声线未就绪";
  }
  if (!reference.voice_generation_ready) {
    return reference.voice_generation_block_reason || "参考声线片段还没有确认归属和授权";
  }
  return null;
}

export function ChatWorkbench() {
  const [profiles, setProfiles] = useState<ProfileSchema[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatRecord[]>([]);
  const [personaItems, setPersonaItems] = useState<PersonaItemSchema[]>([]);
  const [profileStatus, setProfileStatus] = useState<ProfileStatusResponse | null>(null);
  const [skillVersions, setSkillVersions] = useState<SkillVersion[]>([]);
  const [selectedSkillVersionId, setSelectedSkillVersionId] = useState("");
  const [voiceStatus, setVoiceStatus] = useState<VoiceGenerationStatusResponse | null>(null);
  const [voiceReferences, setVoiceReferences] = useState<VoiceReferenceItem[]>([]);
  const [selectedVoiceReferenceId, setSelectedVoiceReferenceId] = useState("");
  const [defaultVoiceReferenceId, setDefaultVoiceReferenceId] = useState("");
  const [voiceReferenceFile, setVoiceReferenceFile] = useState<File | null>(null);
  const [voiceConsentConfirmed, setVoiceConsentConfirmed] = useState(false);
  const [voiceConsentNote, setVoiceConsentNote] = useState("");
  const [voiceGenerationHistory, setVoiceGenerationHistory] = useState<VoiceGenerationRecord[]>([]);
  const [voiceGenerationsByChatId, setVoiceGenerationsByChatId] = useState<Record<string, VoiceGenerationRecord>>({});
  const [voiceAudioUrlsByChatId, setVoiceAudioUrlsByChatId] = useState<Record<string, string>>({});
  const [voiceErrorsByChatId, setVoiceErrorsByChatId] = useState<Record<string, string>>({});
  const [previewAudioUrl, setPreviewAudioUrl] = useState("");
  const [draft, setDraft] = useState("");
  const [chatMode, setChatMode] = useState<ChatMode>("direct");
  const [useModel, setUseModel] = useState(true);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("voice");
  const [isLoading, setIsLoading] = useState(true);
  const [isProfileLoading, setIsProfileLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isClearingHistory, setIsClearingHistory] = useState(false);
  const [isUploadingVoiceReference, setIsUploadingVoiceReference] = useState(false);
  const [extractingVoiceReferenceId, setExtractingVoiceReferenceId] = useState<string | null>(null);
  const [generatingVoiceForRecordId, setGeneratingVoiceForRecordId] = useState<string | null>(null);
  const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);
  const [deletingSkillVersionId, setDeletingSkillVersionId] = useState<string | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<ChatRuntimeStatus | null>(null);
  const [candidateNotice, setCandidateNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? null,
    [profiles, selectedProfileId],
  );
  const visibleMessages = useMemo(() => [...messages].reverse(), [messages]);
  const activeItemCount = useMemo(
    () => personaItems.filter((item) => item.status !== "hidden" && item.status !== "forgotten").length,
    [personaItems],
  );
  const activeMode = chatModeOptions.find((option) => option.value === chatMode) ?? chatModeOptions[0];
  const selectedSkillVersion = skillVersions.find((version) => version.id === selectedSkillVersionId) ?? null;
  const latestSkillVersion = skillVersions[0] ?? null;
  const selectedVoiceReference =
    voiceReferences.find((reference) => reference.raw_source_id === selectedVoiceReferenceId) ?? null;
  const voiceBlockReason = voiceUseBlockReason(voiceStatus, selectedVoiceReference);
  const canUseVoiceReference = !voiceBlockReason;

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    listProfiles()
      .then((items) => {
        if (!isMounted) {
          return;
        }
        setProfiles(items);
        const savedProfileId = readActiveProfileId();
        const nextProfileId =
          savedProfileId && items.some((profile) => profile.id === savedProfileId)
            ? savedProfileId
            : items[0]?.id ?? null;
        setSelectedProfileId(nextProfileId);
        setActiveProfileId(nextProfileId);
      })
      .catch((requestError) => {
        if (isMounted) {
          setError(requestError instanceof Error ? requestError.message : "人物档案加载失败。");
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    getVoiceGenerationStatus()
      .then((status) => {
        if (isMounted) {
          setVoiceStatus(status);
        }
      })
      .catch(() => {
        if (isMounted) {
          setVoiceStatus(null);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedProfileId) {
      setMessages([]);
      setPersonaItems([]);
      setProfileStatus(null);
      setSkillVersions([]);
      setSelectedSkillVersionId("");
      setVoiceReferences([]);
      setSelectedVoiceReferenceId("");
      setDefaultVoiceReferenceId("");
      setVoiceGenerationHistory([]);
      setVoiceGenerationsByChatId({});
      setVoiceAudioUrlsByChatId({});
      return;
    }

    let isMounted = true;
    setIsProfileLoading(true);
    setError(null);
    setVoiceError(null);
    setCandidateNotice(null);
    setRuntimeStatus(null);
    setPreviewAudioUrl("");
    Promise.all([
      listChatMessages(selectedProfileId),
      listPersonaItems(selectedProfileId),
      getProfileStatus(selectedProfileId),
      listSkillVersions(selectedProfileId),
      listRawSources(selectedProfileId),
      listSourceSegments({ profileId: selectedProfileId, ensureMissing: true }),
      listVoiceGenerations(selectedProfileId),
    ])
      .then(([nextMessages, nextItems, nextStatus, nextVersions, rawSources, sourceSegments, voiceGenerations]) => {
        if (!isMounted) {
          return;
        }
        const nextReferences = rawSources
          .map((source) => voiceReferenceFromRawSource(source, sourceSegments))
          .filter((reference): reference is VoiceReferenceItem => Boolean(reference))
          .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at));
        const savedReferenceId = window.localStorage.getItem(defaultVoiceReferenceKey(selectedProfileId));
        const savedReferenceIsValid = Boolean(
          savedReferenceId && nextReferences.some((reference) => reference.raw_source_id === savedReferenceId),
        );
        const preferredReference =
          nextReferences.find((reference) => reference.raw_source_id === savedReferenceId) ??
          nextReferences.find((reference) => reference.voice_generation_ready) ??
          nextReferences.find((reference) => reference.tts_reference_ready) ??
          nextReferences[0] ??
          null;
        const generationMap = voiceGenerations.reduce<Record<string, VoiceGenerationRecord>>((acc, record) => {
          if (record.chat_record_id && !acc[record.chat_record_id]) {
            acc[record.chat_record_id] = record;
          }
          return acc;
        }, {});
        const audioMap = Object.fromEntries(
          Object.values(generationMap)
            .filter((record) => record.status === "success")
            .map((record) => [record.chat_record_id ?? "", voiceGenerationAudioUrl(record.id)])
            .filter(([chatId]) => chatId),
        );

        setMessages(nextMessages);
        setPersonaItems(nextItems);
        setProfileStatus(nextStatus);
        setSkillVersions(nextVersions);
        setSelectedSkillVersionId((current) =>
          current && nextVersions.some((version) => version.id === current) ? current : "",
        );
        setVoiceReferences(nextReferences);
        setSelectedVoiceReferenceId(preferredReference?.raw_source_id ?? "");
        setDefaultVoiceReferenceId(savedReferenceIsValid ? savedReferenceId ?? "" : "");
        setVoiceGenerationHistory(voiceGenerations);
        setVoiceGenerationsByChatId(generationMap);
        setVoiceAudioUrlsByChatId(audioMap);
      })
      .catch((requestError) => {
        if (isMounted) {
          setError(requestError instanceof Error ? requestError.message : "聊天工作台加载失败。");
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsProfileLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [selectedProfileId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [visibleMessages.length, selectedProfileId]);

  function selectVoiceReference(referenceId: string) {
    setSelectedVoiceReferenceId(referenceId);
    setPreviewAudioUrl("");
  }

  function setSelectedVoiceReferenceAsDefault() {
    if (!selectedProfileId || !selectedVoiceReferenceId) {
      return;
    }
    window.localStorage.setItem(defaultVoiceReferenceKey(selectedProfileId), selectedVoiceReferenceId);
    setDefaultVoiceReferenceId(selectedVoiceReferenceId);
  }

  function clearDefaultVoiceReference() {
    if (!selectedProfileId) {
      return;
    }
    window.localStorage.removeItem(defaultVoiceReferenceKey(selectedProfileId));
    setDefaultVoiceReferenceId("");
  }

  async function refreshRuntime(profileId = selectedProfileId) {
    if (!profileId) {
      return;
    }
    const [nextStatus, nextVersions] = await Promise.all([getProfileStatus(profileId), listSkillVersions(profileId)]);
    setProfileStatus(nextStatus);
    setSkillVersions(nextVersions);
    notifyWorkspaceStatusChanged(profileId);
    setSelectedSkillVersionId((current) =>
      current && nextVersions.some((version) => version.id === current) ? current : "",
    );
  }

  async function refreshVoiceWorkspace(profileId = selectedProfileId) {
    if (!profileId) {
      return;
    }
    setVoiceError(null);
    const [nextStatus, rawSources, voiceGenerations] = await Promise.all([
      getVoiceGenerationStatus(),
      listRawSources(profileId),
      listVoiceGenerations(profileId),
    ]);
    const sourceSegments = await listSourceSegments({ profileId, ensureMissing: true });
    const nextReferences = rawSources
      .map((source) => voiceReferenceFromRawSource(source, sourceSegments))
      .filter((reference): reference is VoiceReferenceItem => Boolean(reference))
      .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at));
    const savedReferenceId = window.localStorage.getItem(defaultVoiceReferenceKey(profileId));
    const savedReferenceIsValid = Boolean(
      savedReferenceId && nextReferences.some((reference) => reference.raw_source_id === savedReferenceId),
    );
    const preferredReference =
      nextReferences.find((reference) => reference.raw_source_id === selectedVoiceReferenceId) ??
      nextReferences.find((reference) => reference.raw_source_id === savedReferenceId) ??
      nextReferences.find((reference) => reference.voice_generation_ready) ??
      nextReferences.find((reference) => reference.tts_reference_ready) ??
      nextReferences[0] ??
      null;
    const generationMap = voiceGenerations.reduce<Record<string, VoiceGenerationRecord>>((acc, record) => {
      if (record.chat_record_id && !acc[record.chat_record_id]) {
        acc[record.chat_record_id] = record;
      }
      return acc;
    }, {});
    const audioMap = Object.fromEntries(
      Object.values(generationMap)
        .filter((record) => record.status === "success")
        .map((record) => [record.chat_record_id ?? "", voiceGenerationAudioUrl(record.id)])
        .filter(([chatId]) => chatId),
    );

    setVoiceStatus(nextStatus);
    setVoiceReferences(nextReferences);
    setSelectedVoiceReferenceId(preferredReference?.raw_source_id ?? "");
    setDefaultVoiceReferenceId(savedReferenceIsValid ? savedReferenceId ?? "" : "");
    setVoiceGenerationHistory(voiceGenerations);
    setVoiceGenerationsByChatId(generationMap);
    setVoiceAudioUrlsByChatId(audioMap);
  }

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProfileId || !draft.trim()) {
      return;
    }

    const message = draft.trim();
    setDraft("");
    setIsSending(true);
    setError(null);
    setCandidateNotice(null);
    setRuntimeStatus(null);
    try {
      const response = await chatWithProfile(selectedProfileId, {
        message,
        chat_mode: chatMode,
        use_model: useModel,
        save_record: true,
        skill_version_id: selectedSkillVersionId || null,
      });
      setMessages((current) => [response.record, ...current]);
      setRuntimeStatus(response.runtime_status);
      if (response.candidate_evidence?.created) {
        setCandidateNotice("这条补充已进入待确认区，去 Library 处理后才会成为可用记忆。");
      }
      void getProfileStatus(selectedProfileId).then(setProfileStatus).catch(() => undefined);
    } catch (requestError) {
      setDraft(message);
      setError(requestError instanceof Error ? requestError.message : "发送失败。");
    } finally {
      setIsSending(false);
    }
  }

  function handleDraftKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  async function handleClearHistory() {
    if (!selectedProfileId) {
      return;
    }
    const confirmed = window.confirm("清空当前人物的聊天记录？原始资料、可用记忆和已保存回复版本不会删除。");
    if (!confirmed) {
      return;
    }
    setIsClearingHistory(true);
    setError(null);
    try {
      await clearChatMessages(selectedProfileId);
      setMessages([]);
      setRuntimeStatus(null);
      setCandidateNotice(null);
      notifyWorkspaceStatusChanged(selectedProfileId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "清空聊天记录失败。");
    } finally {
      setIsClearingHistory(false);
    }
  }

  async function handleDeleteSkillVersion(version: SkillVersion) {
    if (!selectedProfileId) {
      return;
    }
    const confirmed = window.confirm(`删除回复版本 "${version.title}"？这不会删除原始资料或可用记忆。`);
    if (!confirmed) {
      return;
    }
    setDeletingSkillVersionId(version.id);
    setError(null);
    try {
      await deleteSkillVersion(selectedProfileId, version.id);
      await refreshRuntime(selectedProfileId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "回复版本删除失败。");
    } finally {
      setDeletingSkillVersionId(null);
    }
  }

  async function handleUploadVoiceReference() {
    if (!selectedProfileId || !voiceReferenceFile) {
      setVoiceError("请先选择人物档案和参考音频/视频。");
      return;
    }
    if (!voiceConsentConfirmed) {
      setVoiceError("必须先确认参考声音/视频授权。");
      return;
    }

    setVoiceError(null);
    setIsUploadingVoiceReference(true);
    try {
      const response = await uploadVoiceReference(
        selectedProfileId,
        voiceReferenceFile,
        voiceConsentConfirmed,
        voiceConsentNote,
      );
      await ensureRawSourceSegments(response.raw_source_id);
      const nextReference = voiceReferenceFromUpload(response);
      setVoiceReferences((current) => [nextReference, ...current.filter((item) => item.raw_source_id !== nextReference.raw_source_id)]);
      selectVoiceReference(nextReference.raw_source_id);
      setVoiceReferenceFile(null);
      setVoiceConsentConfirmed(false);
      notifyWorkspaceStatusChanged(selectedProfileId);
      setVoiceConsentNote("");
      setPreviewAudioUrl("");
      await refreshVoiceWorkspace(selectedProfileId);
    } catch (requestError) {
      setVoiceError(requestError instanceof Error ? requestError.message : "参考音频/视频上传失败。");
    } finally {
      setIsUploadingVoiceReference(false);
    }
  }

  async function handleExtractVoiceReference(reference: VoiceReferenceItem) {
    if (!selectedProfileId) {
      return;
    }
    setVoiceError(null);
    setExtractingVoiceReferenceId(reference.raw_source_id);
    try {
      const response = await extractVoiceReferenceAudio(selectedProfileId, reference.raw_source_id);
      await ensureRawSourceSegments(reference.raw_source_id);
      const nextReference = voiceReferenceFromUpload(response);
      setVoiceReferences((current) =>
        current.map((item) =>
          item.raw_source_id === nextReference.raw_source_id
            ? { ...item, ...nextReference, created_at: item.created_at, consent_note: item.consent_note }
            : item,
        ),
      );
      selectVoiceReference(nextReference.raw_source_id);
      await refreshVoiceWorkspace(selectedProfileId);
    } catch (requestError) {
      setVoiceError(requestError instanceof Error ? requestError.message : "视频参考音频重新抽取失败。");
    } finally {
      setExtractingVoiceReferenceId(null);
    }
  }

  async function handleGenerateVoice(message: ChatRecord) {
    if (!selectedProfileId || !selectedVoiceReference) {
      setVoiceErrorsByChatId((current) => ({ ...current, [message.id]: "请先选择一个已授权参考声音。" }));
      return;
    }
    if (!canUseVoiceReference) {
      setVoiceErrorsByChatId((current) => ({ ...current, [message.id]: voiceBlockReason ?? "当前参考声音不可用。" }));
      return;
    }

    const referenceId = selectedVoiceReference.raw_source_id;
    const consentConfirmed = selectedVoiceReference.consent_confirmed;
    const replyText = message.assistant_message;
    setVoiceErrorsByChatId((current) => ({ ...current, [message.id]: "" }));
    setGeneratingVoiceForRecordId(message.id);
    try {
      const response = await generateAuthorizedVoice(selectedProfileId, {
        reply_text: replyText,
        reference_raw_source_id: referenceId,
        chat_record_id: message.id,
        consent_confirmed: consentConfirmed,
        model: "indextts2",
        generation_notes: "Generated from Chat Workbench. TTS reads fixed assistant reply_text only.",
      });
      setVoiceGenerationsByChatId((current) => ({ ...current, [message.id]: response.record }));
      setVoiceGenerationHistory((current) => [response.record, ...current.filter((record) => record.id !== response.record.id)]);
      if (response.audio_url) {
        setVoiceAudioUrlsByChatId((current) => ({ ...current, [message.id]: response.audio_url ?? "" }));
      }
    } catch (requestError) {
      setVoiceErrorsByChatId((current) => ({
        ...current,
        [message.id]: requestError instanceof Error ? requestError.message : "授权声线生成失败。",
      }));
    } finally {
      setGeneratingVoiceForRecordId(null);
    }
  }

  async function handlePreviewVoice() {
    if (!selectedProfileId || !selectedVoiceReference) {
      setVoiceError("请先选择一个参考声音。");
      return;
    }
    if (!canUseVoiceReference) {
      setVoiceError(voiceBlockReason ?? "当前参考声音不可用。");
      return;
    }

    const referenceId = selectedVoiceReference.raw_source_id;
    const consentConfirmed = selectedVoiceReference.consent_confirmed;
    setVoiceError(null);
    setPreviewAudioUrl("");
    setIsGeneratingPreview(true);
    try {
      const response = await generateAuthorizedVoice(selectedProfileId, {
        reply_text: PREVIEW_TEXT,
        reference_raw_source_id: referenceId,
        chat_record_id: null,
        consent_confirmed: consentConfirmed,
        model: "indextts2",
        generation_notes: "Voice Studio preview. Fixed preview text only.",
      });
      setPreviewAudioUrl(response.audio_url ?? voiceGenerationAudioUrl(response.record.id));
      setVoiceGenerationHistory((current) => [response.record, ...current.filter((record) => record.id !== response.record.id)]);
    } catch (requestError) {
      setVoiceError(requestError instanceof Error ? requestError.message : "声色预览生成失败。");
    } finally {
      setIsGeneratingPreview(false);
    }
  }

  async function handleConfirmVoiceReferenceSegment() {
    if (!selectedProfileId || !selectedVoiceReference) {
      return;
    }
    setVoiceError(null);
    try {
      const segments = selectedVoiceReference.source_segment_id
        ? []
        : await ensureRawSourceSegments(selectedVoiceReference.raw_source_id);
      const segmentId = selectedVoiceReference.source_segment_id ?? segments[0]?.id;
      if (!segmentId) {
        setVoiceError("没有找到可确认的声音片段。");
        return;
      }
      await updateSourceSegment(segmentId, {
        target_person: "target_person",
        attribution_status: "confirmed",
        consent_confirmed: true,
        consent_note: selectedVoiceReference.consent_note || "Confirmed in Voice Studio.",
        permitted_uses: ["voice_reference", "voice_generation"],
        metadata: {
          confirmed_from: "chat_voice_studio",
          confirmed_raw_source_id: selectedVoiceReference.raw_source_id,
        },
      });
      await refreshVoiceWorkspace(selectedProfileId);
    } catch (requestError) {
      setVoiceError(requestError instanceof Error ? requestError.message : "声音片段确认失败。");
    }
  }

  return (
    <div className="flex h-[calc(100dvh-8.5rem)] min-h-0 min-w-0 gap-3 overflow-hidden sm:h-[calc(100dvh-7rem)] lg:h-[calc(100vh-6.5rem)]">
      <aside className="hidden w-72 shrink-0 flex-col overflow-hidden rounded-md border bg-card lg:flex">
        <div className="border-b px-3 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Database className="size-4 text-primary" aria-hidden="true" />
            对象
          </div>
          <div className="mt-1 text-xs text-muted-foreground">切换人物会同步切换聊天、记忆依据、回复版本与声线参考。</div>
        </div>
        <div className="min-h-0 flex-1 space-y-2 overflow-auto p-2">
          {isLoading ? (
            <div className="flex items-center gap-2 px-2 py-3 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              加载中
            </div>
          ) : profiles.length ? (
            profiles.map((profile) => (
              <button
                key={profile.id}
                type="button"
                onClick={() => {
                  setSelectedProfileId(profile.id);
                  setActiveProfileId(profile.id);
                }}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                  profile.id === selectedProfileId ? "border-primary bg-primary text-primary-foreground" : "bg-background hover:bg-muted"
                }`}
              >
                <span className="block truncate font-medium">{profile.display_name}</span>
                <span className="block truncate text-xs opacity-75">{profile.relationship}</span>
              </button>
            ))
          ) : (
            <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">还没有人物档案。</div>
          )}
        </div>
        {profileStatus ? (
          <div className="border-t p-3 text-xs leading-5 text-muted-foreground">
            <div className="font-medium text-foreground">{profileStatus.stage_label}</div>
            <div>资料 {profileStatus.raw_source_count} · 记忆 {profileStatus.persona_item_count}</div>
            <div>待确认 {profileStatus.open_question_count + profileStatus.open_uncertain_count} · 回复版本 {profileStatus.skill_version_count}</div>
          </div>
        ) : null}
      </aside>

      <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-md border bg-card">
        <div className="border-b px-3 py-3">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Bot className="size-5 text-primary" aria-hidden="true" />
                <h1 className="truncate text-base font-semibold">{selectedProfile?.display_name ?? "AI 聊天"}</h1>
                {isProfileLoading ? <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden="true" /> : null}
              </div>
              <div className="mt-1 truncate text-xs text-muted-foreground">{activeMode.description}</div>
            </div>
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <select
                value={selectedProfileId ?? ""}
                onChange={(event) => {
                  const nextProfileId = event.target.value || null;
                  setSelectedProfileId(nextProfileId);
                  setActiveProfileId(nextProfileId);
                }}
                className="h-9 min-w-40 rounded-md border border-input bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
              >
                <option value="">选择人物</option>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.display_name}
                  </option>
                ))}
              </select>
              <div className="inline-flex rounded-md border bg-background p-1">
                {chatModeOptions.map((option) => (
                  <Button
                    key={option.value}
                    type="button"
                    variant={option.value === chatMode ? "default" : "ghost"}
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setChatMode(option.value)}
                  >
                    {option.value === "direct" ? <Bot className="size-3.5" aria-hidden="true" /> : <MessageCircle className="size-3.5" aria-hidden="true" />}
                    {option.label}
                  </Button>
                ))}
              </div>
              <Badge className="border-primary/30 bg-primary/10 text-primary">记忆 {activeItemCount}</Badge>
              <Badge className={canUseVoiceReference ? "border-primary/30 bg-primary/10 text-primary" : "border-muted bg-muted text-muted-foreground"}>
                声音 {canUseVoiceReference ? "可用" : voiceBlockReason}
              </Badge>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8"
                onClick={handleClearHistory}
                disabled={!selectedProfileId || !messages.length || isClearingHistory}
              >
                {isClearingHistory ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Trash2 className="size-4" aria-hidden="true" />}
                清空
              </Button>
            </div>
          </div>
        </div>

        <details className="border-b bg-background p-2 2xl:hidden">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-md border bg-muted/20 px-3 py-2 text-sm font-medium">
            <span className="flex min-w-0 items-center gap-2">
              <Headphones className="size-4 text-primary" aria-hidden="true" />
              <span className="truncate">声音 / 依据</span>
            </span>
            <Badge className={canUseVoiceReference ? "border-primary/30 bg-primary/10 text-primary" : "border-muted bg-muted text-muted-foreground"}>
              {canUseVoiceReference ? "可用" : voiceBlockReason}
            </Badge>
          </summary>
          <div className="mt-2 max-h-[38vh] space-y-3 overflow-auto rounded-md border bg-muted/20 p-3 text-xs leading-5">
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="rounded-md border bg-background p-3 text-muted-foreground">
                <div className="font-medium text-foreground">
                  声音服务 {voiceStatus?.enabled && voiceStatus.configured ? "可用" : "不可用"}
                </div>
                <div>IndexTTS2 {voiceStatus?.enabled ? "已开启" : "未开启"} · 接口{voiceStatus?.configured ? "已配置" : "未配置"}</div>
                <div>视频抽音频 {voiceStatus?.ffmpeg_available ? "可用" : "不可用"} · 视频参考 {voiceStatus?.video_reference_supported ? "可抽取" : "不可用"}</div>
                {voiceStatus?.ffmpeg_error ? <div className="text-destructive">{voiceStatus.ffmpeg_error}</div> : null}
              </div>
              <div className="rounded-md border bg-background p-3 text-muted-foreground">
                <div className="font-medium text-foreground">本次回复</div>
                <div>{runtimeSummary(runtimeStatus)}</div>
                <div>模式：{activeMode.label}</div>
                <div>模型：{useModel ? "接入当前配置" : "不接入模型"}</div>
              </div>
            </div>

            <div className="grid gap-2 rounded-md border bg-background p-3 sm:grid-cols-[minmax(0,1fr)_auto_auto_auto]">
              <select
                value={selectedVoiceReferenceId}
                onChange={(event) => selectVoiceReference(event.target.value)}
                className="h-9 min-w-0 rounded-md border border-input bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">选择参考声线</option>
                {voiceReferences.map((reference) => (
                  <option key={reference.raw_source_id} value={reference.raw_source_id}>
                    {reference.file_name} / {voiceReferenceStatusLabel(reference)}
                  </option>
                ))}
              </select>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9 text-xs"
                onClick={() => {
                  void refreshVoiceWorkspace();
                }}
                disabled={!selectedProfileId}
              >
                <RefreshCw className="size-3.5" aria-hidden="true" />
                刷新
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9 text-xs"
                disabled={!selectedVoiceReferenceId || selectedVoiceReferenceId === defaultVoiceReferenceId}
                onClick={setSelectedVoiceReferenceAsDefault}
              >
                <Check className="size-3.5" aria-hidden="true" />
                默认
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9 text-xs"
                disabled={!defaultVoiceReferenceId}
                onClick={clearDefaultVoiceReference}
              >
                <Trash2 className="size-3.5" aria-hidden="true" />
                清除
              </Button>
            </div>

            <div className="space-y-2 rounded-md border bg-background p-3">
              <div className="flex items-center gap-2 font-medium">
                <Upload className="size-4 text-primary" aria-hidden="true" />
                上传参考音频/视频
              </div>
              <div className="text-muted-foreground">只用于朗读已生成文本，不决定回复内容。</div>
              <input
                type="file"
                accept="audio/*,video/*,.mp3,.wav,.m4a,.aac,.ogg,.flac,.webm,.mp4,.mov,.mkv,.avi,.m4v"
                onChange={(event) => {
                  setVoiceReferenceFile(event.currentTarget.files?.[0] ?? null);
                  setVoiceError(null);
                }}
                className="block w-full text-xs"
              />
              {voiceReferenceFile ? <div className="break-all text-muted-foreground">{voiceReferenceFile.name}</div> : null}
              <label className="flex items-start gap-2 text-muted-foreground">
                <input
                  type="checkbox"
                  checked={voiceConsentConfirmed}
                  onChange={(event) => setVoiceConsentConfirmed(event.target.checked)}
                  className="mt-1"
                />
                <span>确认拥有参考声音/视频授权，并会标记 AI generated。</span>
              </label>
              <textarea
                value={voiceConsentNote}
                onChange={(event) => setVoiceConsentNote(event.target.value)}
                placeholder="授权备注：来源、授权范围、用途"
                className="min-h-16 w-full rounded-md border border-input bg-background px-2 py-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 w-full text-xs"
                disabled={!selectedProfileId || !voiceReferenceFile || !voiceConsentConfirmed || isUploadingVoiceReference}
                onClick={() => {
                  void handleUploadVoiceReference();
                }}
              >
                {isUploadingVoiceReference ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> : <Mic2 className="size-3.5" aria-hidden="true" />}
                保存参考声线
              </Button>
            </div>

            {selectedVoiceReference?.voice_reference_kind === "video" && !selectedVoiceReference.tts_reference_ready ? (
              <div className="space-y-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-950">
                <div className="font-medium">视频参考还不能用于声音生成</div>
                <div>{voiceStatus?.ffmpeg_available ? "可以重试抽取音频。" : "当前 ffmpeg 不可用，无法从视频抽音频。"}</div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 w-full bg-background text-xs"
                  disabled={!voiceStatus?.ffmpeg_available || extractingVoiceReferenceId === selectedVoiceReference.raw_source_id}
                  onClick={() => {
                    void handleExtractVoiceReference(selectedVoiceReference);
                  }}
                >
                  {extractingVoiceReferenceId === selectedVoiceReference.raw_source_id ? (
                    <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                  ) : (
                    <RefreshCw className="size-3.5" aria-hidden="true" />
                  )}
                  重试抽取音频
                </Button>
              </div>
            ) : null}

            <div className="space-y-2 rounded-md border bg-background p-3">
              <div className="font-medium">声色预览</div>
              <div className="text-muted-foreground">{PREVIEW_TEXT}</div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 w-full text-xs"
                disabled={!canUseVoiceReference || isGeneratingPreview}
                onClick={() => {
                  void handlePreviewVoice();
                }}
              >
                {isGeneratingPreview ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> : <Volume2 className="size-3.5" aria-hidden="true" />}
                生成预览
              </Button>
              {!canUseVoiceReference ? <div className="text-muted-foreground">{voiceBlockReason}</div> : null}
              {previewAudioUrl ? <audio controls src={previewAudioUrl} className="w-full min-w-0" /> : null}
            </div>

            <div className="space-y-2 rounded-md border bg-background p-3">
              <div className="flex items-center justify-between">
                <div className="font-medium">最近生成</div>
                <Badge className="border-muted bg-muted text-muted-foreground">{voiceGenerationHistory.length}</Badge>
              </div>
              {voiceGenerationHistory.length ? (
                <div className="space-y-2">
                  {voiceGenerationHistory.slice(0, 4).map((record) => (
                    <div key={record.id} className="rounded-md border bg-muted/20 p-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-medium text-foreground">
                          {record.chat_record_id ? "聊天回复" : "声线预览"}
                        </span>
                        <span className={record.status === "success" ? "text-primary" : "text-destructive"}>{generationStatusLabel(record.status)}</span>
                      </div>
                      <div className="truncate text-muted-foreground">{record.reply_text}</div>
                      {record.status === "success" ? (
                        <audio controls src={voiceGenerationAudioUrl(record.id)} className="mt-2 w-full min-w-0" />
                      ) : record.error ? (
                        <div className="mt-1 text-destructive">{record.error}</div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-md border border-dashed p-3 text-muted-foreground">还没有生成记录。</div>
              )}
            </div>

            {voiceError ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-destructive">{voiceError}</div>
            ) : null}
          </div>
        </details>

        {error ? (
          <div className="border-b border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>
        ) : null}
        {candidateNotice ? (
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary">
            <span>{candidateNotice}</span>
            <Link
              href="/library"
              className="inline-flex h-8 items-center rounded-md border border-primary/30 bg-background px-3 text-xs font-medium text-primary hover:bg-primary/10"
            >
              去确认
            </Link>
          </div>
        ) : null}

        <div className="min-h-0 flex-1 space-y-4 overflow-auto bg-muted/20 p-3">
          {visibleMessages.length ? (
            visibleMessages.map((message) => (
              <div key={message.id} className="space-y-3">
                <div className="ml-auto max-w-[88%] break-words rounded-md bg-primary px-4 py-3 text-sm leading-6 text-primary-foreground">
                  <div className="mb-1 flex items-center gap-2 text-xs opacity-80">
                    <UserRound className="size-3" aria-hidden="true" />
                    你
                  </div>
                  {message.user_message}
                </div>
                <div className="max-w-[88%] break-words rounded-md border bg-background px-4 py-3 text-sm leading-6">
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <Bot className="size-3" aria-hidden="true" />
                    AI
                    <span>{formatDate(message.created_at)}</span>
                    <span>{modeLabel(message.chat_mode)}</span>
                    <span>记忆 {message.used_persona_item_ids.length}</span>
                    <span>资料 {message.used_raw_source_ids.length}</span>
                  </div>
                  <div className="whitespace-pre-wrap">{message.assistant_message}</div>
                  <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md border bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-8 px-2 text-xs"
                      disabled={!canUseVoiceReference || generatingVoiceForRecordId === message.id}
                      onClick={() => {
                        void handleGenerateVoice(message);
                      }}
                    >
                      {generatingVoiceForRecordId === message.id ? (
                        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                      ) : (
                        <Volume2 className="size-3.5" aria-hidden="true" />
                      )}
                      生成声音
                    </Button>
                    <span>{canUseVoiceReference ? "仅读这条回复，不改写内容。" : voiceBlockReason}</span>
                    {voiceGenerationsByChatId[message.id] ? (
                      <span>状态 {generationStatusLabel(voiceGenerationsByChatId[message.id].status)} · AI generated</span>
                    ) : null}
                    {voiceAudioUrlsByChatId[message.id] ? (
                      <audio controls src={voiceAudioUrlsByChatId[message.id]} className="w-full min-w-0" />
                    ) : null}
                    {voiceErrorsByChatId[message.id] ? (
                      <span className="w-full text-destructive">{voiceErrorsByChatId[message.id]}</span>
                    ) : null}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-md border border-dashed bg-background p-6 text-sm leading-6 text-muted-foreground">
              {selectedProfile
                ? chatMode === "third_person"
                  ? "说一个你想起 TA 的场景，我会用旁观者视角陪你整理。"
                  : "发送一句话，测试基于已保存资料和记忆的聊天。"
                : "请先选择一个人物档案。"}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSend} className="border-t bg-background p-3">
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
            <Textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleDraftKeyDown}
              placeholder={chatMode === "third_person" ? "说说你想聊的 TA，或某个场景..." : "发一句话..."}
              className="max-h-32 min-h-12 resize-y"
              disabled={!selectedProfileId || isSending}
            />
            <Button type="submit" className="h-12 shrink-0" disabled={!selectedProfileId || !draft.trim() || isSending}>
              {isSending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Send className="size-4" aria-hidden="true" />}
              发送
            </Button>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <span>{runtimeSummary(runtimeStatus)}</span>
            <label className="inline-flex items-center gap-2">
              <input type="checkbox" checked={useModel} onChange={(event) => setUseModel(event.target.checked)} />
              接入模型
            </label>
          </div>
        </form>
      </section>

      <aside className="hidden w-[360px] shrink-0 flex-col overflow-hidden rounded-md border bg-card 2xl:flex">
        <div className="flex items-center justify-between border-b px-3 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <PanelRight className="size-4 text-primary" aria-hidden="true" />
            声音与依据
          </div>
          <div className="inline-flex rounded-md border bg-background p-1">
            <Button
              type="button"
              variant={inspectorTab === "voice" ? "default" : "ghost"}
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => setInspectorTab("voice")}
            >
              <Headphones className="size-3.5" aria-hidden="true" />
              声音
            </Button>
            <Button
              type="button"
              variant={inspectorTab === "runtime" ? "default" : "ghost"}
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => setInspectorTab("runtime")}
            >
              <Settings2 className="size-3.5" aria-hidden="true" />
              依据
            </Button>
          </div>
        </div>

        {inspectorTab === "voice" ? (
          <div className="min-h-0 flex-1 space-y-3 overflow-auto p-3">
            <div className="rounded-md border bg-muted/20 p-3 text-xs leading-5 text-muted-foreground">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-medium text-foreground">
                    声音服务 {voiceStatus?.enabled && voiceStatus.configured ? "可用" : "不可用"}
                  </div>
                  <div>IndexTTS2 {voiceStatus?.enabled ? "已开启" : "未开启"} · 接口{voiceStatus?.configured ? "已配置" : "未配置"}</div>
                  <div>视频抽音频 {voiceStatus?.ffmpeg_available ? "可用" : "不可用"} · 视频参考 {voiceStatus?.video_reference_supported ? "可抽取" : "不可用"}</div>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 px-2 text-xs"
                  onClick={() => {
                    void refreshVoiceWorkspace();
                  }}
                  disabled={!selectedProfileId}
                >
                  <RefreshCw className="size-3.5" aria-hidden="true" />
                  刷新
                </Button>
              </div>
              {voiceStatus?.ffmpeg_path ? <div className="mt-2 break-all">{voiceStatus.ffmpeg_path}</div> : null}
              {voiceStatus?.ffmpeg_error ? <div className="mt-1 text-destructive">{voiceStatus.ffmpeg_error}</div> : null}
              {voiceStatus?.safety ? <div className="mt-1">{voiceStatus.safety}</div> : null}
            </div>

            <div className="space-y-2 rounded-md border bg-background p-3 text-xs leading-5">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-medium">当前声线</div>
                  <div className="text-muted-foreground">
                    {selectedVoiceReference ? selectedVoiceReference.file_name : "还没有选择参考声线"}
                  </div>
                </div>
                <Badge className={canUseVoiceReference ? "border-primary/30 bg-primary/10 text-primary" : "border-muted bg-muted text-muted-foreground"}>
                  {canUseVoiceReference ? "可生成" : "不可用"}
                </Badge>
              </div>
              <div className="rounded-md bg-muted/40 px-2 py-1 text-muted-foreground">
                {canUseVoiceReference ? "预览和消息转语音都会使用这条参考声线。" : voiceBlockReason}
              </div>
              {selectedVoiceReference && !selectedVoiceReference.voice_generation_ready ? (
                <div className="rounded-md border border-amber-200 bg-amber-50 px-2 py-2 text-amber-950">
                  <div className="font-medium">需要确认声音片段</div>
                  <div>
                    只有确认这段声音属于当前人物，并允许用于 AI 生成声音后，才能预览或朗读回复。
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="mt-2 h-8 bg-background text-xs"
                    disabled={!selectedVoiceReference.tts_reference_ready}
                    onClick={() => {
                      void handleConfirmVoiceReferenceSegment();
                    }}
                  >
                    <Check className="size-3.5" aria-hidden="true" />
                    确认归属并允许声音生成
                  </Button>
                  {!selectedVoiceReference.tts_reference_ready ? (
                    <div className="mt-1 text-xs">先让参考音频就绪，再确认片段授权。</div>
                  ) : null}
                </div>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs"
                  disabled={!selectedVoiceReferenceId || selectedVoiceReferenceId === defaultVoiceReferenceId}
                  onClick={setSelectedVoiceReferenceAsDefault}
                >
                  设为默认
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs"
                  disabled={!defaultVoiceReferenceId}
                  onClick={clearDefaultVoiceReference}
                >
                  清除默认
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">参考声线</div>
                <Badge className="border-muted bg-muted text-muted-foreground">{voiceReferences.length}</Badge>
              </div>
              {voiceReferences.length ? (
                <div className="space-y-2">
                  {voiceReferences.map((reference) => (
                    <button
                      key={reference.raw_source_id}
                      type="button"
                      onClick={() => selectVoiceReference(reference.raw_source_id)}
                      className={`w-full rounded-md border px-3 py-2 text-left text-xs leading-5 transition-colors ${
                        reference.raw_source_id === selectedVoiceReferenceId
                          ? "border-primary bg-primary/10"
                          : "bg-background hover:bg-muted"
                      }`}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate font-medium text-foreground">{reference.file_name}</span>
                        <span className="flex items-center gap-1">
                          {reference.raw_source_id === defaultVoiceReferenceId ? (
                            <Badge className="border-primary/30 bg-primary/10 text-primary">默认</Badge>
                          ) : null}
                          {reference.raw_source_id === selectedVoiceReferenceId ? <Check className="size-4 text-primary" aria-hidden="true" /> : null}
                        </span>
                      </span>
                      <span className="block text-muted-foreground">
                        {reference.voice_reference_kind} · {voiceReferenceStatusLabel(reference)} · {formatDate(reference.created_at)}
                      </span>
                      <span className="block text-muted-foreground">
                        片段：{reference.segment_target_person} / {reference.segment_attribution_status}
                      </span>
                      {reference.voice_generation_block_reason ? (
                        <span className="block text-amber-700">{reference.voice_generation_block_reason}</span>
                      ) : null}
                      {reference.audio_extraction_error ? <span className="block text-destructive">{reference.audio_extraction_error}</span> : null}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">还没有授权参考声音。</div>
              )}
            </div>

            <div className="space-y-2 rounded-md border bg-background p-3 text-xs leading-5">
              <div className="flex items-center gap-2 font-medium">
                <Upload className="size-4 text-primary" aria-hidden="true" />
                上传参考音频/视频
              </div>
              <div className="text-muted-foreground">这里保存授权参考声线，只用于朗读已生成文本，不决定说什么。</div>
              <input
                type="file"
                accept="audio/*,video/*,.mp3,.wav,.m4a,.aac,.ogg,.flac,.webm,.mp4,.mov,.mkv,.avi,.m4v"
                onChange={(event) => {
                  setVoiceReferenceFile(event.currentTarget.files?.[0] ?? null);
                  setVoiceError(null);
                }}
                className="block w-full text-xs"
              />
              {voiceReferenceFile ? <div className="break-all text-muted-foreground">{voiceReferenceFile.name}</div> : null}
              <label className="flex items-start gap-2 text-muted-foreground">
                <input
                  type="checkbox"
                  checked={voiceConsentConfirmed}
                  onChange={(event) => setVoiceConsentConfirmed(event.target.checked)}
                  className="mt-1"
                />
                <span>我确认拥有参考声音/视频授权，并会标记 AI generated。</span>
              </label>
              <textarea
                value={voiceConsentNote}
                onChange={(event) => setVoiceConsentNote(event.target.value)}
                placeholder="授权备注：来源、授权范围、用途"
                className="min-h-16 w-full rounded-md border border-input bg-background px-2 py-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 w-full text-xs"
                disabled={!selectedProfileId || !voiceReferenceFile || !voiceConsentConfirmed || isUploadingVoiceReference}
                onClick={() => {
                  void handleUploadVoiceReference();
                }}
              >
                {isUploadingVoiceReference ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> : <Mic2 className="size-3.5" aria-hidden="true" />}
                保存参考声线
              </Button>
              {!voiceReferenceFile ? <div className="text-muted-foreground">请选择音频或视频参考声线。</div> : null}
              {voiceReferenceFile && !voiceConsentConfirmed ? <div className="text-amber-700">确认授权后才能保存。</div> : null}
            </div>

            {selectedVoiceReference?.voice_reference_kind === "video" && !selectedVoiceReference.tts_reference_ready ? (
              <div className="space-y-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-950">
                <div className="font-medium">视频参考还不能用于声音生成</div>
                <div>{voiceStatus?.ffmpeg_available ? "可以重试抽取音频。" : "当前 ffmpeg 不可用，无法从视频抽音频。"}</div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 w-full bg-background text-xs"
                  disabled={!voiceStatus?.ffmpeg_available || extractingVoiceReferenceId === selectedVoiceReference.raw_source_id}
                  onClick={() => {
                    void handleExtractVoiceReference(selectedVoiceReference);
                  }}
                >
                  {extractingVoiceReferenceId === selectedVoiceReference.raw_source_id ? (
                    <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                  ) : (
                    <RefreshCw className="size-3.5" aria-hidden="true" />
                  )}
                  重试抽取音频
                </Button>
              </div>
            ) : null}

            <div className="space-y-2 rounded-md border bg-background p-3 text-xs leading-5">
              <div className="font-medium">声色预览</div>
              <div className="text-muted-foreground">{PREVIEW_TEXT}</div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 w-full text-xs"
                disabled={!canUseVoiceReference || isGeneratingPreview}
                onClick={() => {
                  void handlePreviewVoice();
                }}
              >
                {isGeneratingPreview ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> : <Volume2 className="size-3.5" aria-hidden="true" />}
                生成预览
              </Button>
              {!canUseVoiceReference ? <div className="text-muted-foreground">{voiceBlockReason}</div> : null}
              {previewAudioUrl ? <audio controls src={previewAudioUrl} className="w-full min-w-0" /> : null}
            </div>

            <div className="space-y-2 rounded-md border bg-background p-3 text-xs leading-5">
              <div className="flex items-center justify-between">
                <div className="font-medium">最近生成</div>
                <Badge className="border-muted bg-muted text-muted-foreground">{voiceGenerationHistory.length}</Badge>
              </div>
              {voiceGenerationHistory.length ? (
                <div className="space-y-2">
                  {voiceGenerationHistory.slice(0, 6).map((record) => (
                    <div key={record.id} className="rounded-md border bg-muted/20 p-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-medium text-foreground">
                          {record.chat_record_id ? "聊天回复" : "声线预览"}
                        </span>
                        <span className={record.status === "success" ? "text-primary" : "text-destructive"}>{generationStatusLabel(record.status)}</span>
                      </div>
                      <div className="truncate text-muted-foreground">{record.reply_text}</div>
                      <div className="text-muted-foreground">{formatDate(record.created_at)} · AI generated</div>
                      {record.status === "success" ? (
                        <audio controls src={voiceGenerationAudioUrl(record.id)} className="mt-2 w-full min-w-0" />
                      ) : record.error ? (
                        <div className="mt-1 text-destructive">{record.error}</div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-md border border-dashed p-3 text-muted-foreground">还没有生成记录。</div>
              )}
            </div>

            {voiceError ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">{voiceError}</div>
            ) : null}
          </div>
        ) : (
          <div className="min-h-0 flex-1 space-y-3 overflow-auto p-3">
            <div className="rounded-md border bg-muted/20 p-3 text-xs leading-5 text-muted-foreground">
              <div className="font-medium text-foreground">{profileStatus?.stage_label ?? "未选择人物"}</div>
              <div>{profileStatus?.next_action ?? "选择人物后显示下一步。"}</div>
              {profileStatus ? (
                <div className="mt-2 grid grid-cols-4 gap-2 text-center">
                  <div className="rounded border bg-background p-2">
                    <div className="font-semibold text-foreground">{profileStatus.raw_source_count}</div>
                    <div>资料</div>
                  </div>
                  <div className="rounded border bg-background p-2">
                    <div className="font-semibold text-foreground">{profileStatus.persona_item_count}</div>
                    <div>记忆</div>
                  </div>
                  <div className="rounded border bg-background p-2">
                    <div className="font-semibold text-foreground">{profileStatus.open_question_count + profileStatus.open_uncertain_count}</div>
                    <div>待确认</div>
                  </div>
                  <div className="rounded border bg-background p-2">
                    <div className="font-semibold text-foreground">{profileStatus.skill_version_count}</div>
                    <div>版本</div>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="space-y-2 rounded-md border bg-background p-3 text-xs leading-5">
              <div className="font-medium">回复版本</div>
              <select
                value={selectedSkillVersionId}
                onChange={(event) => setSelectedSkillVersionId(event.target.value)}
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">即时生成回复依据</option>
                {skillVersions.map((version) => (
                  <option key={version.id} value={version.id}>
                    {version.title} / {formatDate(version.created_at)}
                  </option>
                ))}
              </select>
              {selectedSkillVersion ?? latestSkillVersion ? (
                <div className="text-muted-foreground">
                  依据 {(selectedSkillVersion ?? latestSkillVersion)?.evidence_unit_count} · 待审 {(selectedSkillVersion ?? latestSkillVersion)?.audit_count} · 问题 {(selectedSkillVersion ?? latestSkillVersion)?.question_backlog_count}
                </div>
              ) : (
                <div className="text-muted-foreground">暂无保存回复版本；仍可按当前资料即时生成依据。</div>
              )}
              {selectedSkillVersion ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 border-destructive/30 text-xs text-destructive hover:bg-destructive/10"
                  disabled={deletingSkillVersionId === selectedSkillVersion.id}
                  onClick={() => {
                    void handleDeleteSkillVersion(selectedSkillVersion);
                  }}
                >
                  {deletingSkillVersionId === selectedSkillVersion.id ? (
                    <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                  ) : (
                    <Trash2 className="size-3.5" aria-hidden="true" />
                  )}
                  删除当前版本
                </Button>
              ) : null}
            </div>

            <div className="space-y-2 rounded-md border bg-background p-3 text-xs leading-5 text-muted-foreground">
              <div className="font-medium text-foreground">本次回复</div>
              <div>{runtimeSummary(runtimeStatus)}</div>
              <div>模式：{activeMode.label}</div>
              <div>模型：{useModel ? "接入当前配置" : "不接入模型"}</div>
              <div>聊天发现只会进入候选记忆，不会自动变成确认事实。</div>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
