"use client";

import Link from "next/link";
import { type ClipboardEvent, type DragEvent, type FormEvent, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileText,
  Image as ImageIcon,
  Loader2,
  MessageSquareText,
  Music,
  PlusCircle,
  RefreshCw,
  Sparkles,
  UserPlus,
  Video,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useLanguage } from "@/components/language-provider";
import {
  createProfile,
  deleteSkillVersion,
  generateSkill,
  getProfileStatus,
  ingestFile,
  ingestSkill,
  listSkillVersions,
  listProfiles,
  reextractRawSource,
  saveSkillVersion,
  type IngestResponse,
  type ProfileStatusResponse,
  type ProfileSchema,
  type RelationshipType,
  type SkillGenerationResponse,
  type SkillVersion,
  type SourceType,
} from "@/lib/api";
import { relationshipOptions, starterContent, type CopyDocumentKind } from "@/features/dashboard/config";
import { buildCopyDocument, copyText, downloadSkillExport } from "@/features/dashboard/export-documents";
import { DashboardResultPanels } from "@/features/dashboard/result-panels";
import {
  AUDIO_ACCEPT,
  IMAGE_ACCEPT,
  MAX_UPLOAD_BYTES,
  VIDEO_ACCEPT,
  isAudioUpload,
  isImageUpload,
  isVideoUpload,
  sourceTypeFromUpload,
} from "@/features/dashboard/upload";
import { notifyWorkspaceStatusChanged, readActiveProfileId, setActiveProfileId } from "@/lib/workspace-state";

type MaterialKind = "text" | "chat" | "file" | "audio" | "video" | "image" | "interview";

type MaterialOption = {
  value: MaterialKind;
  title: string;
  description: string;
  icon: LucideIcon;
  mode: "text" | "upload";
  sourceType: SourceType;
};

const materialOptions: MaterialOption[] = [
  {
    value: "text",
    title: "文本",
    description: "粘贴回忆、信件、备注或手写补充。",
    icon: FileText,
    mode: "text",
    sourceType: "text",
  },
  {
    value: "chat",
    title: "聊天记录",
    description: "粘贴聊天片段，保留说话方式和关系语境。",
    icon: MessageSquareText,
    mode: "text",
    sourceType: "chat",
  },
  {
    value: "audio",
    title: "音频",
    description: "上传录音做转写入库；参考声线在 Chat 声音面板授权使用。",
    icon: Music,
    mode: "upload",
    sourceType: "audio",
  },
  {
    value: "video",
    title: "视频",
    description: "上传视频作为资料备注；参考声线走 Chat 声音面板抽取音频。",
    icon: Video,
    mode: "upload",
    sourceType: "file",
  },
  {
    value: "image",
    title: "图片",
    description: "上传截图或照片，配置视觉模型后可识别文字和场景。",
    icon: ImageIcon,
    mode: "upload",
    sourceType: "image",
  },
  {
    value: "file",
    title: "文件",
    description: "PDF、文档、文本文件或其他资料。",
    icon: Database,
    mode: "upload",
    sourceType: "file",
  },
  {
    value: "interview",
    title: "访谈补充",
    description: "用你的话补充关系、场景、边界和原话。",
    icon: ClipboardCheck,
    mode: "text",
    sourceType: "interview",
  },
];

export default function DashboardPage() {
  const { t } = useLanguage();
  const [sourceType, setSourceType] = useState<SourceType>("file");
  const [materialKind, setMaterialKind] = useState<MaterialKind>("text");
  const [content, setContent] = useState(starterContent);
  const [upload, setUpload] = useState<File | null>(null);
  const [uploadNotes, setUploadNotes] = useState("");
  const [uploadPreviewUrl, setUploadPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [profiles, setProfiles] = useState<ProfileSchema[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [newProfileName, setNewProfileName] = useState("");
  const [newProfileRelationship, setNewProfileRelationship] = useState<RelationshipType>("family");
  const [newProfileDescription, setNewProfileDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [profileLoadError, setProfileLoadError] = useState<string | null>(null);
  const [copiedKind, setCopiedKind] = useState<CopyDocumentKind | null>(null);
  const [profileStatus, setProfileStatus] = useState<ProfileStatusResponse | null>(null);
  const [skillResult, setSkillResult] = useState<SkillGenerationResponse | null>(null);
  const [skillVersions, setSkillVersions] = useState<SkillVersion[]>([]);
  const [skillError, setSkillError] = useState<string | null>(null);
  const [skillCopiedKind, setSkillCopiedKind] = useState<"markdown" | "json" | null>(null);
  const [isDraggingUpload, setIsDraggingUpload] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCreatingProfile, setIsCreatingProfile] = useState(false);
  const [isGeneratingSkill, setIsGeneratingSkill] = useState(false);
  const [isSavingSkillVersion, setIsSavingSkillVersion] = useState(false);
  const [deletingSkillVersionId, setDeletingSkillVersionId] = useState<string | null>(null);
  const [isReextracting, setIsReextracting] = useState(false);
  const [isProfileCreatorOpen, setIsProfileCreatorOpen] = useState(false);

  const piiTotal = useMemo(() => {
    if (!result) {
      return 0;
    }
    return Object.values(result.pii_summary).reduce((sum, count) => sum + count, 0);
  }, [result]);
  const uploadIsImage = upload ? isImageUpload(upload) : false;
  const uploadIsAudio = upload ? isAudioUpload(upload) : false;
  const uploadIsVideo = upload ? isVideoUpload(upload) : false;
  const selectedProfile = profiles.find((profile) => profile.id === selectedProfileId) ?? null;
  const selectedMaterial = materialOptions.find((option) => option.value === materialKind) ?? materialOptions[0];
  const usesUpload = selectedMaterial.mode === "upload";
  const hasProfileProcessingIssue = Boolean(
    profileStatus && profileStatus.raw_source_count > 0 && profileStatus.persona_item_count === 0,
  );
  const latestResultNoPersonaItems = Boolean(result && result.persona_items.length === 0);
  const recentSegmentCount =
    typeof result?.diagnostics.source_segment_count === "number" ? result.diagnostics.source_segment_count : 0;
  const recentSegmentStatus =
    typeof result?.diagnostics.segment_attribution_status === "string"
      ? result.diagnostics.segment_attribution_status
      : "";
  const dashboardStats = [
    { label: "资料", value: profileStatus?.raw_source_count ?? 0 },
    { label: "可用条目", value: profileStatus?.persona_item_count ?? 0 },
    { label: "待确认", value: (profileStatus?.open_question_count ?? 0) + (profileStatus?.open_uncertain_count ?? 0) },
    { label: "版本", value: profileStatus?.skill_version_count ?? 0 },
  ];

  const materialAccept =
    materialKind === "audio"
      ? AUDIO_ACCEPT
      : materialKind === "video"
        ? VIDEO_ACCEPT
        : materialKind === "image"
          ? IMAGE_ACCEPT
          : undefined;

  useEffect(() => {
    if (!upload || (!isImageUpload(upload) && !isAudioUpload(upload) && !isVideoUpload(upload))) {
      setUploadPreviewUrl(null);
      return;
    }

    const nextUrl = URL.createObjectURL(upload);
    setUploadPreviewUrl(nextUrl);
    return () => URL.revokeObjectURL(nextUrl);
  }, [upload]);

  useEffect(() => {
    setSourceType(selectedMaterial.sourceType);
    setError(null);
  }, [selectedMaterial.sourceType]);

  useEffect(() => {
    let isMounted = true;
    listProfiles()
      .then((items) => {
        if (!isMounted) {
          return;
        }
        setProfileLoadError(null);
        setProfiles(items);
        const savedProfileId = readActiveProfileId();
        const nextProfileId =
          savedProfileId && items.some((item) => item.id === savedProfileId)
            ? savedProfileId
            : items[0]?.id ?? null;
        setSelectedProfileId(nextProfileId);
        setActiveProfileId(nextProfileId);
      })
      .catch((requestError) => {
        if (!isMounted) {
          return;
        }
        setProfileLoadError(requestError instanceof Error ? requestError.message : "人物档案加载失败。");
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    setSkillResult(null);
    setSkillError(null);
    setSkillCopiedKind(null);
  }, [selectedProfileId]);

  useEffect(() => {
    if (!selectedProfileId) {
      setProfileStatus(null);
      setSkillVersions([]);
      return;
    }
    let isMounted = true;
    Promise.all([getProfileStatus(selectedProfileId), listSkillVersions(selectedProfileId)])
      .then(([nextStatus, nextVersions]) => {
        if (!isMounted) {
          return;
        }
        setProfileStatus(nextStatus);
        setSkillVersions(nextVersions);
      })
      .catch(() => {
        if (isMounted) {
          setProfileStatus(null);
          setSkillVersions([]);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [selectedProfileId]);

  async function refreshProfiles(preferredProfileId?: string) {
    const items = await listProfiles();
    setProfileLoadError(null);
    setProfiles(items);
    const nextProfileId =
      preferredProfileId && items.some((profile) => profile.id === preferredProfileId)
        ? preferredProfileId
        : selectedProfileId && items.some((profile) => profile.id === selectedProfileId)
          ? selectedProfileId
          : items[0]?.id ?? null;
    setSelectedProfileId(nextProfileId);
    setActiveProfileId(nextProfileId);
  }

  async function refreshStatus(profileId = selectedProfileId) {
    if (!profileId) {
      setProfileStatus(null);
      setSkillVersions([]);
      return;
    }
    const [nextStatus, nextVersions] = await Promise.all([getProfileStatus(profileId), listSkillVersions(profileId)]);
    setProfileStatus(nextStatus);
    setSkillVersions(nextVersions);
    notifyWorkspaceStatusChanged(profileId);
  }

  async function handleCreateProfile() {
    const displayName = newProfileName.trim();
    if (!displayName) {
      setError(t.profileNameRequired);
      return;
    }

    setError(null);
    setIsCreatingProfile(true);
    try {
      const profile = await createProfile({
        display_name: displayName,
        relationship: newProfileRelationship,
        description: newProfileDescription.trim(),
      });
      setNewProfileName("");
      setNewProfileDescription("");
      setIsProfileCreatorOpen(false);
      await refreshProfiles(profile.id);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t.profileCreateError);
    } finally {
      setIsCreatingProfile(false);
    }
  }

  function relationshipLabel(relationship: RelationshipType) {
    const option = relationshipOptions.find((item) => item.value === relationship);
    return option ? t[option.labelKey] : t.relationshipOther;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const response = await ingestSkill({
        source_type: sourceType,
        raw_content: content,
        metadata: {
          submitted_from: "dashboard",
          architecture_layer: "raw_source_to_persona_items",
        },
        profile_id: selectedProfileId,
      });
      setResult(response);
      await refreshProfiles(selectedProfileId ?? undefined);
      await refreshStatus(selectedProfileId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t.ingestError);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleUploadSubmit() {
    setError(null);
    if (!upload) {
      setError(t.uploadRequired);
      return;
    }
    if (upload.size > MAX_UPLOAD_BYTES) {
      setError(t.uploadTooLarge);
      return;
    }

    setIsSubmitting(true);
    try {
      setResult(await ingestFile(upload, uploadNotes, selectedProfileId));
      setSourceType(sourceTypeFromUpload(upload));
      await refreshProfiles(selectedProfileId ?? undefined);
      await refreshStatus(selectedProfileId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t.ingestError);
    } finally {
      setIsSubmitting(false);
    }
  }

  function materialKindFromFile(file: File): MaterialKind {
    if (isAudioUpload(file)) {
      return "audio";
    }
    if (isVideoUpload(file)) {
      return "video";
    }
    if (isImageUpload(file)) {
      return "image";
    }
    return "file";
  }

  function handleSelectMaterial(nextKind: MaterialKind) {
    setMaterialKind(nextKind);
    setError(null);
  }

  function selectUploadFile(file: File | null) {
    if (!file) {
      return;
    }
    setError(null);
    setUpload(file);
    setMaterialKind(materialKindFromFile(file));
  }

  function handleUploadInputChange(event: FormEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    selectUploadFile(input.files?.[0] ?? null);
    input.value = "";
  }

  function handleUploadDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDraggingUpload(false);
    selectUploadFile(event.dataTransfer.files?.[0] ?? null);
  }

  function handleUploadDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setIsDraggingUpload(true);
  }

  function handleUploadDragLeave(event: DragEvent<HTMLDivElement>) {
    const nextTarget = event.relatedTarget;
    if (nextTarget instanceof Node && event.currentTarget.contains(nextTarget)) {
      return;
    }
    setIsDraggingUpload(false);
  }

  function handleUploadPaste(event: ClipboardEvent<HTMLDivElement>) {
    const clipboardFiles = Array.from(event.clipboardData.files);
    const itemFile = Array.from(event.clipboardData.items)
      .find((item) => item.kind === "file")
      ?.getAsFile();
    selectUploadFile(clipboardFiles[0] ?? itemFile ?? null);
  }

  async function handleReextractLatest() {
    if (!result) {
      return;
    }
    setError(null);
    setIsReextracting(true);
    try {
      const response = await reextractRawSource(result.raw_source.id);
      setResult(response);
      await refreshStatus(selectedProfileId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "重新提取失败。");
    } finally {
      setIsReextracting(false);
    }
  }

  async function handleCopyDocument(kind: CopyDocumentKind) {
    if (!result) {
      return;
    }

    await copyText(buildCopyDocument(result, kind));
    setCopiedKind(kind);
    window.setTimeout(() => setCopiedKind(null), 1600);
  }

  function buildSkillJson() {
    if (!skillResult) {
      return "";
    }

    return JSON.stringify(skillResult, null, 2);
  }

  function downloadTextFile(text: string, fileName: string, type: string) {
    const blob = new Blob([text], { type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function skillFilePrefix() {
    const profileName = selectedProfile?.display_name.trim() || selectedProfileId || "profile";
    const safeProfileName = profileName.replace(/[^\w.-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 48) || "profile";
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    return `generated-skill-${safeProfileName}-${timestamp}`;
  }

  async function handleGenerateSkill() {
    if (!selectedProfileId) {
      setSkillError("请先选择一个人物，再生成回复版本。");
      return;
    }

    setSkillError(null);
    setIsGeneratingSkill(true);
    try {
      setSkillResult(await generateSkill(selectedProfileId, true));
      await refreshStatus(selectedProfileId);
    } catch (requestError) {
      setSkillError(requestError instanceof Error ? requestError.message : "回复版本生成失败，请检查后端服务。");
    } finally {
      setIsGeneratingSkill(false);
    }
  }

  async function handleSaveSkillVersion() {
    if (!selectedProfileId || !skillResult) {
      return;
    }
    setSkillError(null);
    setIsSavingSkillVersion(true);
    try {
      await saveSkillVersion(selectedProfileId, {
        title: `${selectedProfile?.display_name ?? "人物"} 回复版本`,
        skill: skillResult,
      });
      await refreshStatus(selectedProfileId);
    } catch (requestError) {
      setSkillError(requestError instanceof Error ? requestError.message : "回复版本保存失败。");
    } finally {
      setIsSavingSkillVersion(false);
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
    setSkillError(null);
    setDeletingSkillVersionId(version.id);
    try {
      await deleteSkillVersion(selectedProfileId, version.id);
      await refreshStatus(selectedProfileId);
    } catch (requestError) {
      setSkillError(requestError instanceof Error ? requestError.message : "回复版本删除失败。");
    } finally {
      setDeletingSkillVersionId(null);
    }
  }

  async function handleCopySkill(kind: "markdown" | "json") {
    if (!skillResult) {
      return;
    }

    const text = kind === "markdown" ? skillResult.skill_markdown : buildSkillJson();
    await copyText(text);
    setSkillCopiedKind(kind);
    window.setTimeout(() => setSkillCopiedKind(null), 1600);
  }

  function handleDownloadSkill(kind: "markdown" | "json") {
    if (!skillResult) {
      return;
    }

    const prefix = skillFilePrefix();
    if (kind === "markdown") {
      downloadTextFile(skillResult.skill_markdown, `${prefix}.md`, "text/markdown;charset=utf-8");
      return;
    }
    downloadTextFile(buildSkillJson(), `${prefix}.json`, "application/json;charset=utf-8");
  }

  const nextAction = selectedProfile
    ? profileStatus?.next_action ?? "添加一段资料，系统会先保存原始材料，再尝试提取可用条目。"
    : "先选择或新建一个人物，再添加资料。";
  const canSubmitText = Boolean(selectedProfileId && content.trim() && !isSubmitting);
  const canSubmitUpload = Boolean(selectedProfileId && upload && !isSubmitting);
  const recentSourceType = result?.raw_source.source_type ?? null;
  const recentSourceName = result?.raw_source.file_name || result?.raw_source.metadata?.filename;
  const recentSourceLabel = typeof recentSourceName === "string" && recentSourceName.trim() ? recentSourceName : recentSourceType ?? "本次资料";
  const recentExtractionStatus =
    typeof result?.raw_source.metadata?.extraction_status === "string" ? result.raw_source.metadata.extraction_status : "";
  const recentExtractionProvider =
    typeof result?.raw_source.metadata?.extraction_provider === "string" ? result.raw_source.metadata.extraction_provider : "";
  const recentExtractionError =
    typeof result?.raw_source.metadata?.extraction_error === "string" ? result.raw_source.metadata.extraction_error : "";
  const recentExtractionHint =
    typeof result?.raw_source.metadata?.extraction_hint === "string" ? result.raw_source.metadata.extraction_hint : "";
  const recentExtractionLabel =
    recentExtractionStatus === "recognized"
      ? "已识别"
      : recentExtractionStatus === "disabled"
        ? "未启用"
        : recentExtractionStatus === "not_configured"
          ? "未配置"
          : recentExtractionStatus === "failed"
            ? "识别失败"
            : recentExtractionStatus;

  return (
    <div className="grid h-full min-h-0 gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="min-h-0 space-y-4 overflow-auto pr-0 xl:pr-1">
        <Card>
          <CardContent className="p-4">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
              <div className="min-w-0 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge className="border-primary/30 bg-primary/10 text-primary">资料工作台</Badge>
                  {profileStatus ? <Badge className="bg-background text-foreground">{profileStatus.stage_label}</Badge> : null}
                  {hasProfileProcessingIssue ? (
                    <Badge className="border-amber-200 bg-amber-50 text-amber-900">需要处理</Badge>
                  ) : null}
                </div>
                <div>
                  <h1 className="text-xl font-semibold tracking-normal">给人物添加资料</h1>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    先选人物，再添加文本、音频、视频、图片或聊天记录。系统会先保存原始资料，再尝试提取可用条目。
                  </p>
                </div>
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                  {materialOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => handleSelectMaterial(option.value)}
                      className={`rounded-md border p-3 text-left transition-colors ${
                        materialKind === option.value ? "border-primary bg-primary/10" : "bg-background hover:bg-muted"
                      }`}
                    >
                      <span className="flex items-center gap-2 text-sm font-medium">
                        <option.icon className="size-4 text-primary" aria-hidden="true" />
                        {option.title}
                      </span>
                      <span className="mt-1 block text-xs leading-5 text-muted-foreground">{option.description}</span>
                    </button>
                  ))}
                </div>
                <div className="grid gap-2 sm:grid-cols-4">
                  {dashboardStats.map((item) => (
                    <div key={item.label} className="rounded-md border bg-background px-3 py-1.5">
                      <div className="text-base font-semibold">{item.value}</div>
                      <div className="text-xs text-muted-foreground">{item.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-2 rounded-md border bg-background p-3">
                <Label htmlFor="profile-select">当前人物</Label>
                <select
                  id="profile-select"
                  value={selectedProfileId ?? ""}
                  onChange={(event) => {
                    const nextProfileId = event.target.value || null;
                    setSelectedProfileId(nextProfileId);
                    setActiveProfileId(nextProfileId);
                  }}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="">{t.noProfileOption}</option>
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.display_name} / {relationshipLabel(profile.relationship)}
                    </option>
                  ))}
                </select>
                {selectedProfile ? (
                  <div className="rounded-md bg-muted/40 px-3 py-2 text-xs leading-5 text-muted-foreground">
                    <div className="font-medium text-foreground">{selectedProfile.display_name}</div>
                    <div>{selectedProfile.description || "暂无备注"}</div>
                  </div>
                ) : null}
                {profileLoadError ? (
                  <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    {profileLoadError}
                  </div>
                ) : null}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => setIsProfileCreatorOpen((current) => !current)}
                >
                  <PlusCircle className="size-4" aria-hidden="true" />
                  {isProfileCreatorOpen ? "收起新建人物" : "新建人物"}
                </Button>
                {isProfileCreatorOpen ? (
                  <div className="space-y-2 border-t pt-2">
                    <Input
                      value={newProfileName}
                      onChange={(event) => setNewProfileName(event.target.value)}
                      placeholder={t.profileNamePlaceholder}
                    />
                    <select
                      value={newProfileRelationship}
                      onChange={(event) => setNewProfileRelationship(event.target.value as RelationshipType)}
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      {relationshipOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {t[option.labelKey]}
                        </option>
                      ))}
                    </select>
                    <Textarea
                      value={newProfileDescription}
                      onChange={(event) => setNewProfileDescription(event.target.value)}
                      className="min-h-16 text-sm leading-6"
                      placeholder={t.profileDescriptionPlaceholder}
                    />
                    <Button type="button" className="w-full" onClick={handleCreateProfile} disabled={isCreatingProfile}>
                      {isCreatingProfile ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <UserPlus className="size-4" aria-hidden="true" />}
                      创建并选择
                    </Button>
                  </div>
                ) : null}
              </div>
            </div>

            <div className={`mt-4 rounded-md border px-3 py-2 text-sm ${hasProfileProcessingIssue ? "border-amber-200 bg-amber-50 text-amber-950" : "bg-muted/30"}`}>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <span className="font-medium">下一步：</span>
                  <span className={hasProfileProcessingIssue ? "" : "text-muted-foreground"}>{nextAction}</span>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  {hasProfileProcessingIssue && result ? (
                    <Button type="button" size="sm" variant="outline" onClick={handleReextractLatest} disabled={isReextracting}>
                      {isReextracting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />}
                      重新提取本次资料
                    </Button>
                  ) : null}
                  {hasProfileProcessingIssue ? (
                    <Link
                      href="/library"
                      className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
                    >
                      查看资料库
                    </Link>
                  ) : null}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">添加资料</CardTitle>
            <CardDescription>选择材料类型后，页面只显示当前任务需要的入口。</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              {usesUpload ? (
                <div
                  className={`grid gap-3 rounded-md border bg-background p-4 outline-none transition-colors ${
                    isDraggingUpload ? "border-primary bg-primary/5" : ""
                  }`}
                  onDragOver={handleUploadDragOver}
                  onDragLeave={handleUploadDragLeave}
                  onDrop={handleUploadDrop}
                  onPaste={handleUploadPaste}
                  tabIndex={0}
                >
                  <div className="space-y-1">
                    <Label htmlFor="upload-source">{selectedMaterial.title}资料</Label>
                    <p className="text-xs leading-5 text-muted-foreground">
                      {materialKind === "audio"
                        ? "这里用于转写、提取记忆和生成声音特征候选；作为授权参考声线请到 Chat 的声音面板上传。"
                        : materialKind === "video"
                          ? "这里保存视频资料和备注；视频参考声线在 Chat 声音面板上传并抽取音频。"
                          : "上传后会先保存原始资料，再尝试提取可用内容。"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <label
                      htmlFor="upload-source"
                      className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                    >
                      <FileText className="size-4" aria-hidden="true" />
                      选择{selectedMaterial.title}资料
                    </label>
                    <input
                      id="upload-source"
                      type="file"
                      accept={materialAccept}
                      onChange={handleUploadInputChange}
                      className="sr-only"
                    />
                    {(materialKind === "audio" || materialKind === "video") ? (
                      <Link
                        href="/chat"
                        className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
                      >
                        <Music className="size-4" aria-hidden="true" />
                        去声音面板做参考声线
                      </Link>
                    ) : null}
                  </div>
                  {upload ? (
                    <div className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
                      <div className="flex items-center gap-2 font-medium text-foreground">
                        {uploadIsImage ? (
                          <ImageIcon className="size-4" aria-hidden="true" />
                        ) : uploadIsAudio ? (
                          <Music className="size-4" aria-hidden="true" />
                        ) : uploadIsVideo ? (
                          <Video className="size-4" aria-hidden="true" />
                        ) : (
                          <FileText className="size-4" aria-hidden="true" />
                        )}
                        {t.selectedFileLabel}: {upload.name} ({Math.round(upload.size / 1024)} KB)
                      </div>
                      <div className="mt-1">{t.uploadReady}</div>
                      {uploadPreviewUrl && uploadIsImage ? (
                        <div className="mt-3">
                          <div className="mb-2 text-xs font-medium text-muted-foreground">{t.imagePreviewLabel}</div>
                          {/* eslint-disable-next-line @next/next/no-img-element -- Local object URLs cannot be optimized by next/image. */}
                          <img src={uploadPreviewUrl} alt={upload.name} className="max-h-56 w-full rounded-md border object-contain" />
                        </div>
                      ) : null}
                      {uploadPreviewUrl && uploadIsAudio ? (
                        <div className="mt-3">
                          <div className="mb-2 text-xs font-medium text-muted-foreground">{t.audioPreviewLabel}</div>
                          <audio controls src={uploadPreviewUrl} className="w-full min-w-0" />
                        </div>
                      ) : null}
                      {uploadPreviewUrl && uploadIsVideo ? (
                        <div className="mt-3">
                          <div className="mb-2 text-xs font-medium text-muted-foreground">视频预览</div>
                          <video controls src={uploadPreviewUrl} className="max-h-64 w-full rounded-md border bg-black" />
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  <div className="grid gap-2">
                    <Label htmlFor="upload-notes">{t.uploadNotesLabel}</Label>
                    <Textarea
                      id="upload-notes"
                      value={uploadNotes}
                      onChange={(event) => setUploadNotes(event.target.value)}
                      className="min-h-24 resize-y text-sm leading-6"
                      placeholder={t.uploadNotesPlaceholder}
                    />
                  </div>
                </div>
              ) : (
                <div className="grid gap-2">
                  <Label htmlFor="raw-content">{selectedMaterial.title}内容</Label>
                  <Textarea
                    id="raw-content"
                    value={content}
                    onChange={(event) => setContent(event.target.value)}
                    className="min-h-40 resize-y text-sm leading-6"
                    placeholder={
                      materialKind === "chat"
                        ? "粘贴聊天片段，尽量保留说话人、时间、上下文。"
                        : materialKind === "interview"
                          ? "写下关系、场景、TA 的原话、不能触碰的边界。"
                          : t.rawContentPlaceholder
                    }
                  />
                </div>
              )}

              {error ? (
                <div className="whitespace-pre-wrap rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              ) : null}

              <div className="flex flex-wrap gap-2">
                {usesUpload ? (
                  <Button type="button" disabled={!canSubmitUpload} onClick={handleUploadSubmit}>
                    {isSubmitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <FileText className="size-4" aria-hidden="true" />}
                    上传并处理
                  </Button>
                ) : (
                  <Button type="submit" disabled={!canSubmitText}>
                    {isSubmitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Sparkles className="size-4" aria-hidden="true" />}
                    保存并提取
                  </Button>
                )}
                {!selectedProfileId ? (
                  <span className="flex items-center text-sm text-muted-foreground">请先选择人物。</span>
                ) : null}
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              {result ? (
                latestResultNoPersonaItems ? (
                  <AlertTriangle className="size-4 text-amber-600" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="size-4 text-primary" aria-hidden="true" />
                )
              ) : (
                <Database className="size-4 text-primary" aria-hidden="true" />
              )}
              最近处理结果
            </CardTitle>
            <CardDescription>只显示刚才这次提交的结果和下一步动作。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {result ? (
              <>
                <div className="grid gap-2 sm:grid-cols-3">
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">保存</div>
                    <div className="mt-1 text-sm font-medium">已保存</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">提取条目</div>
                    <div className="mt-1 text-sm font-medium">{result.persona_items.length}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">片段</div>
                    <div className="mt-1 truncate text-sm font-medium">
                      {recentSegmentCount ? `${recentSegmentCount} · ${recentSegmentStatus || "pending"}` : String(recentSourceLabel)}
                    </div>
                  </div>
                </div>
                {recentSegmentCount ? (
                  <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm leading-6 text-muted-foreground">
                    本次资料已建立片段记录，默认需要人工确认归属后才会作为目标人物证据或声线参考使用。
                  </div>
                ) : null}
                {recentSourceType === "image" && recentExtractionStatus ? (
                  <div
                    className={
                      recentExtractionStatus === "recognized"
                        ? "rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-sm leading-6 text-primary"
                        : "rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-950"
                    }
                  >
                    <div className="font-medium">图片识别：{recentExtractionLabel}</div>
                    {recentExtractionProvider ? <div>服务：{recentExtractionProvider}</div> : null}
                    {recentExtractionError ? <div className="break-all">原因：{recentExtractionError}</div> : null}
                    {recentExtractionHint ? <div>{recentExtractionHint}</div> : null}
                  </div>
                ) : null}
                {latestResultNoPersonaItems ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-950">
                    本次资料已保存，但没有生成可用条目。常见原因是模型未配置、内容太少、无法识别、分类被拒绝或后端返回了提取错误。
                  </div>
                ) : (
                  <div className="rounded-md border bg-primary/5 px-3 py-2 text-sm text-primary">
                    本次资料已进入当前人物，可去 Library 复查证据，也可以继续补充资料。
                  </div>
                )}
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={handleReextractLatest} disabled={isReextracting}>
                    {isReextracting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />}
                    重新提取
                  </Button>
                  <Link
                    href="/library"
                    className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
                  >
                    去确认片段/复查资料
                  </Link>
                  <Link
                    href="/chat"
                    className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
                  >
                    去聊天测试
                  </Link>
                </div>
              </>
            ) : (
              <div className="rounded-md border border-dashed p-4 text-sm leading-6 text-muted-foreground">
                还没有本次处理结果。选择人物并添加资料后，这里会显示保存、提取、失败原因和下一步按钮。
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <aside className="min-h-0 overflow-auto">
        <details className="rounded-md border bg-card p-3">
          <summary className="cursor-pointer text-sm font-medium">处理详情、隐私检查和回复版本</summary>
          <div className="mt-3">
            <DashboardResultPanels
              result={result}
              piiTotal={piiTotal}
              copiedKind={copiedKind}
              selectedProfileName={selectedProfile?.display_name ?? null}
              selectedProfileId={selectedProfileId}
              profileStatus={profileStatus}
              skillResult={skillResult}
              skillError={skillError}
              skillCopiedKind={skillCopiedKind}
              skillVersions={skillVersions}
              isGeneratingSkill={isGeneratingSkill}
              isSavingSkillVersion={isSavingSkillVersion}
              deletingSkillVersionId={deletingSkillVersionId}
              t={t}
              onCopyDocument={handleCopyDocument}
              onDownloadIngestExport={() => downloadSkillExport(result)}
              onGenerateSkill={handleGenerateSkill}
              onSaveSkillVersion={handleSaveSkillVersion}
              onDeleteSkillVersion={handleDeleteSkillVersion}
              onCopySkill={handleCopySkill}
              onDownloadSkill={handleDownloadSkill}
            />
          </div>
        </details>
      </aside>
    </div>
  );
}
