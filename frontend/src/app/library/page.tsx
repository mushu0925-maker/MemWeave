"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { CheckSquare, Database, FileText, HelpCircle, Layers3, Loader2, MessageCircle, Pencil, PlusCircle, RotateCcw, Save, Trash2, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useLanguage } from "@/components/language-provider";
import {
  actOnUncertainItem,
  answerQuestionTarget,
  backfillSourceSegments,
  deleteProfile,
  deletePersonaItem,
  deleteRawSource,
  getProfile,
  getProfileStatus,
  ensureRawSourceSegments,
  listQuestionTargets,
  listUncertainItems,
  listPersonaItems,
  listProfiles,
  listRawSources,
  listSourceSegments,
  purgePersonaItem,
  purgeRawSource,
  reextractRawSource,
  restorePersonaItem,
  restoreRawSource,
  updateSourceSegment,
  updateProfile,
  type LibraryGroup,
  type PersonaItemSchema,
  type ProfileDetailResponse,
  type ProfileStatusResponse,
  type ProfileSchema,
  type QuestionTargetSchema,
  type RawSourceSchema,
  type RelationshipType,
  type SegmentTargetPerson,
  type SourceSegmentSchema,
  type SourceSegmentUpdate,
  type ConfirmationOption,
  type UncertainItemSchema,
} from "@/lib/api";
import { notifyWorkspaceStatusChanged, readActiveProfileId, setActiveProfileId } from "@/lib/workspace-state";

type LibraryView = "review" | "segments" | "items" | "sources" | "trash";
type SegmentAction = "target_evidence" | "target_voice" | "user" | "other" | "unknown" | "reject";
type SegmentFilter = "needs_review" | "confirmed_target" | "voice_ready" | "rejected" | "all";

const relationshipKeys: Record<RelationshipType, "relationshipFamily" | "relationshipFriend" | "relationshipPartner" | "relationshipMentor" | "relationshipSelf" | "relationshipOther"> = {
  family: "relationshipFamily",
  friend: "relationshipFriend",
  partner: "relationshipPartner",
  mentor: "relationshipMentor",
  self: "relationshipSelf",
  other: "relationshipOther",
};

const relationshipOptions: Array<{
  value: RelationshipType;
  labelKey: "relationshipFamily" | "relationshipFriend" | "relationshipPartner" | "relationshipMentor" | "relationshipSelf" | "relationshipOther";
}> = [
  { value: "family", labelKey: "relationshipFamily" },
  { value: "friend", labelKey: "relationshipFriend" },
  { value: "partner", labelKey: "relationshipPartner" },
  { value: "mentor", labelKey: "relationshipMentor" },
  { value: "self", labelKey: "relationshipSelf" },
  { value: "other", labelKey: "relationshipOther" },
];

const groupLabels: Record<LibraryGroup, string> = {
  A: "A 事实记忆库",
  B: "B 语言风格库",
  C: "C 情绪反应库",
  D: "D 性格特质库",
  E: "E 价值观/世界观库",
  F: "F 关系模式库",
  G: "G 决策逻辑库",
  H: "H 冲突/防御库",
  I: "I 关心/陪伴库",
  J: "J 场景反应库",
  K: "K 成长/变化库",
  L: "L 边界/置信库",
  M: "M 声纹/语音特征库",
};

const groupOrder: LibraryGroup[] = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M"];

const uncertainActionLabels: Record<ConfirmationOption, string> = {
  keep: "保留",
  correct: "纠正",
  downrank: "降权",
  hide: "隐藏",
  forget: "遗忘",
};

const uncertainActionDescriptions: Record<ConfirmationOption, string> = {
  keep: "作为可用证据保留",
  correct: "按你的修正文案记录",
  downrank: "只作为低置信上下文",
  hide: "保留审计但不用于聊天或回复版本",
  forget: "不用于聊天或回复版本",
};

const uncertainActionResultText: Record<ConfirmationOption, string> = {
  keep: "保存为确认资料，并尝试重新提取为可用记忆。",
  correct: "保存你的修正文案，再尝试重新提取为可用记忆。",
  downrank: "只更新使用策略，不生成稳定记忆。",
  hide: "保留来源和审计痕迹，但排除聊天和回复版本使用。",
  forget: "保留处理记录，但后续聊天和回复版本不再使用它。",
};

const allUncertainActions: ConfirmationOption[] = ["keep", "correct", "downrank", "hide", "forget"];

const libraryViews: Array<{ value: LibraryView; label: string; description: string }> = [
  { value: "review", label: "待确认", description: "回答、纠正、隐藏或遗忘不确定记忆" },
  { value: "segments", label: "片段确认", description: "确认资料属于谁，以及能否用于证据或声线" },
  { value: "items", label: "可用记忆", description: "查看已提取的记忆和证据来源" },
  { value: "sources", label: "原始资料", description: "复查原始资料并重新提取" },
  { value: "trash", label: "回收站", description: "独立恢复或彻底删除" },
];

const questionReasonLabels: Record<string, string> = {
  missing: "缺失信息",
  low_confidence: "低置信",
  conflict: "证据冲突",
  needs_example: "需要例子",
  needs_boundary: "需要边界",
};

const questionReasonDescriptions: Record<string, string> = {
  missing: "当前记忆库缺少这一类可追溯证据。",
  low_confidence: "已有线索不足以直接写成稳定画像。",
  conflict: "不同证据之间可能不一致，需要你确认。",
  needs_example: "需要具体场景、原话或行为例子来支撑。",
  needs_boundary: "需要明确哪些内容不能说、不能暗示、不能编造。",
};

const uncertainRiskLabels: Record<string, string> = {
  unclear: "不清楚",
  low_confidence: "低置信",
  conflict: "冲突",
  negative_memory: "负面记忆",
  sensitive: "敏感",
  unsupported_fact: "未证实事实",
};

const uncertainRiskDescriptions: Record<string, string> = {
  unclear: "语义或上下文还不够明确。",
  low_confidence: "证据强度不足，不能直接升级为稳定人格判断。",
  conflict: "可能和已有记录冲突，需要人工确认。",
  negative_memory: "可能包含痛苦或负面记忆，应由你决定如何使用。",
  sensitive: "可能涉及敏感内容，需要更严格的边界。",
  unsupported_fact: "像事实陈述，但当前证据不足。",
};

const questionStatusLabels: Record<string, string> = {
  open: "待回答",
  answered: "已回答",
  dismissed: "已关闭",
  resolved: "已解决",
};

const uncertainStatusLabels: Record<string, string> = {
  open: "待处理",
  resolved: "已解决",
  forgotten: "已遗忘",
  hidden: "已隐藏",
};

const segmentTargetLabels: Record<SegmentTargetPerson, string> = {
  target_person: "当前人物",
  user: "用户本人",
  other: "其他人",
  unknown: "未确认",
};

const segmentStatusLabels: Record<string, string> = {
  pending: "待确认",
  confirmed: "已确认",
  rejected: "已拒绝",
  needs_review: "需复查",
};

const segmentUseLabels: Record<string, string> = {
  evidence_review: "复查证据",
  persona_evidence: "写入记忆依据",
  voice_reference: "声线参考",
  voice_generation: "声音生成",
  audit_only: "仅审计",
  voice_reference_review: "声线参考复查",
};

const segmentFilterOptions: Array<{ value: SegmentFilter; label: string; description: string }> = [
  { value: "needs_review", label: "待确认", description: "还不能当作当前人物证据" },
  { value: "confirmed_target", label: "当前人物", description: "已确认可作为资料依据" },
  { value: "voice_ready", label: "可声线", description: "已授权 voice reference/generation" },
  { value: "rejected", label: "已拒绝", description: "仅保留审计记录" },
  { value: "all", label: "全部", description: "查看所有片段状态" },
];

function labelFromMap(map: Record<string, string>, value: string) {
  return map[value] ?? value;
}

function getTargetLabel(group: LibraryGroup, libraryKey: string) {
  return `${groupLabels[group]} / ${libraryKey}`;
}

function getExpectedEvidenceText(value: string) {
  return value.trim() || "具体场景、原话、行为或边界说明";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function groupPersonaItems(items: PersonaItemSchema[]) {
  return groupOrder.map((group) => ({
    group,
    label: groupLabels[group],
    items: items.filter((item) => item.library_group === group),
  }));
}

function isVisiblePersonaItem(item: PersonaItemSchema) {
  return (
    item.status !== "hidden" &&
    item.status !== "forgotten" &&
    item.extraction_method !== "local_fallback_after_model_failed" &&
    item.library_key !== "relationship_exit_strategy"
  );
}

function getMetadataText(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key];
  return typeof value === "string" ? value.trim() : "";
}

function getRawSourceQuestion(source: RawSourceSchema) {
  if (getMetadataText(source.metadata, "source") !== "question_target_answer") {
    return "";
  }
  return getMetadataText(source.metadata, "question");
}

function segmentLoadErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : "片段接口不可用。";
  return `片段接口不可用：${message}。请重启后端；旧后端不会影响已保存资料，但片段确认暂时不可用。`;
}

function isVoiceReferenceSource(source: RawSourceSchema | undefined) {
  return Boolean(source?.metadata.voice_reference);
}

function sourceTitle(source: RawSourceSchema | undefined) {
  if (!source) {
    return "未知资料";
  }
  return source.file_name || `${source.source_type} 资料`;
}

function segmentPurposeText(segment: SourceSegmentSchema, source: RawSourceSchema | undefined) {
  if (isVoiceReferenceSource(source) || segment.metadata.purpose === "voice_reference") {
    return "声线参考";
  }
  return "资料证据";
}

function segmentNeedsReview(segment: SourceSegmentSchema) {
  return segment.attribution_status === "pending" || segment.attribution_status === "needs_review";
}

function segmentVoiceReady(segment: SourceSegmentSchema) {
  return (
    segment.attribution_status === "confirmed" &&
    segment.target_person === "target_person" &&
    segment.consent_confirmed &&
    (segment.permitted_uses.includes("voice_generation") || segment.permitted_uses.includes("voice_reference"))
  );
}

function segmentEvidenceReady(segment: SourceSegmentSchema) {
  return (
    segment.attribution_status === "confirmed" &&
    segment.target_person === "target_person" &&
    segment.permitted_uses.includes("persona_evidence")
  );
}

function segmentEffectText(segment: SourceSegmentSchema) {
  if (segment.attribution_status === "rejected") {
    return "结果：仅保留审计记录，不作为当前人物证据，也不能作为声线参考。";
  }
  if (segmentVoiceReady(segment)) {
    return "结果：可作为当前人物资料证据，并且可作为已授权声线参考用于声音生成。";
  }
  if (segmentEvidenceReady(segment)) {
    return "结果：可作为当前人物资料证据；不会用于声线生成。";
  }
  if (segment.target_person === "user" || segment.target_person === "other") {
    return "结果：已确认不属于当前人物，只保留审计和来源复查。";
  }
  return "结果：仍待确认，暂不进入当前人物证据链，也不能作为声线参考。";
}

function segmentActionPayload(action: SegmentAction, segment: SourceSegmentSchema): SourceSegmentUpdate {
  if (action === "target_voice") {
    return {
      target_person: "target_person",
      attribution_status: "confirmed",
      consent_confirmed: true,
      consent_note: segment.consent_note || "用户在 Library 确认该片段属于当前人物，并允许用于 AI 声音生成。",
      permitted_uses: ["voice_reference", "voice_generation"],
      metadata: { confirmed_from: "library_segments", confirmed_use: "voice_generation" },
    };
  }
  if (action === "target_evidence") {
    return {
      target_person: "target_person",
      attribution_status: "confirmed",
      consent_confirmed: true,
      consent_note: segment.consent_note || "用户在 Library 确认该片段属于当前人物，可作为资料证据使用。",
      permitted_uses: ["evidence_review", "persona_evidence"],
      metadata: { confirmed_from: "library_segments", confirmed_use: "persona_evidence" },
    };
  }
  if (action === "reject") {
    return {
      attribution_status: "rejected",
      permitted_uses: ["audit_only"],
      metadata: { confirmed_from: "library_segments", rejection_reason: "user_rejected_segment" },
    };
  }
  return {
    target_person: action,
    attribution_status: action === "unknown" ? "needs_review" : "confirmed",
    consent_confirmed: false,
    permitted_uses: ["audit_only"],
    metadata: { confirmed_from: "library_segments", confirmed_use: "audit_only" },
  };
}

export default function LibraryPage() {
  const { t } = useLanguage();
  const [profiles, setProfiles] = useState<ProfileSchema[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<LibraryView>("review");
  const [detail, setDetail] = useState<ProfileDetailResponse | null>(null);
  const [profileStatus, setProfileStatus] = useState<ProfileStatusResponse | null>(null);
  const [rawSources, setRawSources] = useState<RawSourceSchema[]>([]);
  const [personaItems, setPersonaItems] = useState<PersonaItemSchema[]>([]);
  const [deletedRawSources, setDeletedRawSources] = useState<RawSourceSchema[]>([]);
  const [deletedPersonaItems, setDeletedPersonaItems] = useState<PersonaItemSchema[]>([]);
  const [uncertainItems, setUncertainItems] = useState<UncertainItemSchema[]>([]);
  const [questionTargets, setQuestionTargets] = useState<QuestionTargetSchema[]>([]);
  const [sourceSegments, setSourceSegments] = useState<SourceSegmentSchema[]>([]);
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isDeletingProfile, setIsDeletingProfile] = useState(false);
  const [reextractingSourceId, setReextractingSourceId] = useState<string | null>(null);
  const [mutatingTrashId, setMutatingTrashId] = useState<string | null>(null);
  const [profileLoadError, setProfileLoadError] = useState<string | null>(null);
  const [profileEditError, setProfileEditError] = useState<string | null>(null);
  const [reextractError, setReextractError] = useState<string | null>(null);
  const [trashError, setTrashError] = useState<string | null>(null);
  const [questionAnswers, setQuestionAnswers] = useState<Record<string, string>>({});
  const [submittingQuestionId, setSubmittingQuestionId] = useState<string | null>(null);
  const [questionAnswerError, setQuestionAnswerError] = useState<string | null>(null);
  const [questionAnswerNotice, setQuestionAnswerNotice] = useState<string | null>(null);
  const [uncertainCorrections, setUncertainCorrections] = useState<Record<string, string>>({});
  const [uncertainNotes, setUncertainNotes] = useState<Record<string, string>>({});
  const [mutatingUncertainId, setMutatingUncertainId] = useState<string | null>(null);
  const [uncertainActionError, setUncertainActionError] = useState<string | null>(null);
  const [uncertainActionNotice, setUncertainActionNotice] = useState<string | null>(null);
  const [mutatingSegmentId, setMutatingSegmentId] = useState<string | null>(null);
  const [isBackfillingSegments, setIsBackfillingSegments] = useState(false);
  const [bulkSegmentAction, setBulkSegmentAction] = useState<SegmentAction | null>(null);
  const [selectedSegmentIds, setSelectedSegmentIds] = useState<string[]>([]);
  const [segmentFilter, setSegmentFilter] = useState<SegmentFilter>("needs_review");
  const [segmentError, setSegmentError] = useState<string | null>(null);
  const [segmentNotice, setSegmentNotice] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editRelationship, setEditRelationship] = useState<RelationshipType>("other");
  const [editDescription, setEditDescription] = useState("");
  const [editBoundaries, setEditBoundaries] = useState("");

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? null,
    [profiles, selectedProfileId],
  );
  const visiblePersonaItems = useMemo(() => personaItems.filter(isVisiblePersonaItem), [personaItems]);
  const groupedPersonaItems = useMemo(() => groupPersonaItems(visiblePersonaItems), [visiblePersonaItems]);
  const openQuestionCount = useMemo(
    () => questionTargets.filter((target) => target.status === "open").length,
    [questionTargets],
  );
  const openUncertainCount = useMemo(
    () => uncertainItems.filter((item) => item.status === "open").length,
    [uncertainItems],
  );
  const rawSourcesById = useMemo(
    () => new Map(rawSources.map((source) => [source.id, source])),
    [rawSources],
  );
  const sourceSegmentsByRawSourceId = useMemo(() => {
    const grouped = new Map<string, SourceSegmentSchema[]>();
    for (const segment of sourceSegments) {
      const current = grouped.get(segment.raw_source_id) ?? [];
      current.push(segment);
      grouped.set(segment.raw_source_id, current);
    }
    return grouped;
  }, [sourceSegments]);
  const pendingSegmentCount = useMemo(
    () => sourceSegments.filter(segmentNeedsReview).length,
    [sourceSegments],
  );
  const confirmedTargetSegmentCount = useMemo(
    () => sourceSegments.filter((segment) => segment.attribution_status === "confirmed" && segment.target_person === "target_person").length,
    [sourceSegments],
  );
  const voiceReadySegmentCount = useMemo(
    () => sourceSegments.filter(segmentVoiceReady).length,
    [sourceSegments],
  );
  const rejectedSegmentCount = useMemo(
    () => sourceSegments.filter((segment) => segment.attribution_status === "rejected").length,
    [sourceSegments],
  );
  const segmentFilterCounts = useMemo(
    () => ({
      needs_review: sourceSegments.filter(segmentNeedsReview).length,
      confirmed_target: confirmedTargetSegmentCount,
      voice_ready: voiceReadySegmentCount,
      rejected: rejectedSegmentCount,
      all: sourceSegments.length,
    }),
    [confirmedTargetSegmentCount, rejectedSegmentCount, sourceSegments, voiceReadySegmentCount],
  );
  const filteredSourceSegments = useMemo(
    () =>
      sourceSegments
        .filter((segment) => {
          if (segmentFilter === "needs_review") {
            return segmentNeedsReview(segment);
          }
          if (segmentFilter === "confirmed_target") {
            return segment.attribution_status === "confirmed" && segment.target_person === "target_person";
          }
          if (segmentFilter === "voice_ready") {
            return segmentVoiceReady(segment);
          }
          if (segmentFilter === "rejected") {
            return segment.attribution_status === "rejected";
          }
          return true;
        })
        .sort((left, right) => {
          const leftPending = segmentNeedsReview(left) ? 0 : 1;
          const rightPending = segmentNeedsReview(right) ? 0 : 1;
          if (leftPending !== rightPending) {
            return leftPending - rightPending;
          }
          return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
        }),
    [segmentFilter, sourceSegments],
  );
  const selectedSegments = useMemo(
    () => filteredSourceSegments.filter((segment) => selectedSegmentIds.includes(segment.id)),
    [filteredSourceSegments, selectedSegmentIds],
  );

  useEffect(() => {
    const validIds = new Set(sourceSegments.map((segment) => segment.id));
    setSelectedSegmentIds((current) => current.filter((id) => validIds.has(id)));
  }, [sourceSegments]);

  useEffect(() => {
    let isMounted = true;
    setIsLoadingProfiles(true);
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
        setProfiles([]);
        setSelectedProfileId(null);
      })
      .finally(() => {
        if (isMounted) {
          setIsLoadingProfiles(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedProfileId) {
      setDetail(null);
      setProfileStatus(null);
      setRawSources([]);
      setPersonaItems([]);
      setDeletedRawSources([]);
      setDeletedPersonaItems([]);
      setUncertainItems([]);
      setQuestionTargets([]);
      setSourceSegments([]);
      setQuestionAnswers({});
      setQuestionAnswerError(null);
      setQuestionAnswerNotice(null);
      setUncertainCorrections({});
      setUncertainNotes({});
      setUncertainActionError(null);
      setUncertainActionNotice(null);
      setSelectedSegmentIds([]);
      setSegmentError(null);
      setSegmentNotice(null);
      return;
    }

    let isMounted = true;
    setIsLoadingDetail(true);
    Promise.all([
      getProfile(selectedProfileId),
      getProfileStatus(selectedProfileId),
      listRawSources(selectedProfileId),
      listPersonaItems(selectedProfileId),
      listRawSources(selectedProfileId, { deletedOnly: true }),
      listPersonaItems(selectedProfileId, { deletedOnly: true }),
      listUncertainItems(selectedProfileId),
      listQuestionTargets(selectedProfileId),
      listSourceSegments({ profileId: selectedProfileId, ensureMissing: true }).catch((error) => {
        if (isMounted) {
          setSegmentError(segmentLoadErrorMessage(error));
        }
        return [] as SourceSegmentSchema[];
      }),
    ])
      .then(([
        nextDetail,
        nextStatus,
        nextRawSources,
        nextPersonaItems,
        nextDeletedRawSources,
        nextDeletedPersonaItems,
        nextUncertainItems,
        nextQuestionTargets,
        nextSourceSegments,
      ]) => {
        if (!isMounted) {
          return;
        }
        setDetail(nextDetail);
        setProfileStatus(nextStatus);
        setRawSources(nextRawSources);
        setPersonaItems(nextPersonaItems);
        setDeletedRawSources(nextDeletedRawSources);
        setDeletedPersonaItems(nextDeletedPersonaItems);
        setUncertainItems(nextUncertainItems);
        setQuestionTargets(nextQuestionTargets);
        setSourceSegments(nextSourceSegments);
        setQuestionAnswers({});
        setQuestionAnswerError(null);
        setQuestionAnswerNotice(null);
        setUncertainCorrections({});
        setUncertainNotes({});
        setUncertainActionError(null);
        setUncertainActionNotice(null);
        if (nextSourceSegments.length) {
          setSegmentError(null);
        }
        setSegmentNotice(null);
      })
      .finally(() => {
        if (isMounted) {
          setIsLoadingDetail(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [selectedProfileId]);

  useEffect(() => {
    if (!selectedProfile) {
      setIsEditingProfile(false);
      setProfileEditError(null);
      setEditName("");
      setEditRelationship("other");
      setEditDescription("");
      setEditBoundaries("");
      return;
    }

    setProfileEditError(null);
    setEditName(selectedProfile.display_name);
    setEditRelationship(selectedProfile.relationship);
    setEditDescription(selectedProfile.description);
    setEditBoundaries(selectedProfile.boundaries.join("\n"));
  }, [selectedProfile]);

  async function refreshProfileState(profileId: string) {
    const [
      items,
      nextDetail,
      nextStatus,
      nextRawSources,
      nextPersonaItems,
      nextDeletedRawSources,
      nextDeletedPersonaItems,
      nextSourceSegments,
    ] = await Promise.all([
      listProfiles(),
      getProfile(profileId),
      getProfileStatus(profileId),
      listRawSources(profileId),
      listPersonaItems(profileId),
      listRawSources(profileId, { deletedOnly: true }),
      listPersonaItems(profileId, { deletedOnly: true }),
      listSourceSegments({ profileId, ensureMissing: true }).catch((error) => {
        setSegmentError(segmentLoadErrorMessage(error));
        return [] as SourceSegmentSchema[];
      }),
    ]);
    const [nextUncertainItems, nextQuestionTargets] = await Promise.all([
      listUncertainItems(profileId),
      listQuestionTargets(profileId),
    ]);
    setProfileLoadError(null);
    setProfiles(items);
    setDetail(nextDetail);
    setProfileStatus(nextStatus);
    setRawSources(nextRawSources);
    setPersonaItems(nextPersonaItems);
    setDeletedRawSources(nextDeletedRawSources);
    setDeletedPersonaItems(nextDeletedPersonaItems);
    setUncertainItems(nextUncertainItems);
    setQuestionTargets(nextQuestionTargets);
    setSourceSegments(nextSourceSegments);
    if (nextSourceSegments.length) {
      setSegmentError(null);
    }
    setSelectedProfileId(profileId);
    setActiveProfileId(profileId);
    notifyWorkspaceStatusChanged(profileId);
  }

  async function refreshProfilesAfterDelete() {
    const items = await listProfiles();
    setProfileLoadError(null);
    setProfiles(items);
    const nextProfileId = items[0]?.id ?? null;
    setSelectedProfileId(nextProfileId);
    setActiveProfileId(nextProfileId);
    notifyWorkspaceStatusChanged(nextProfileId);
    if (!nextProfileId) {
      setDetail(null);
      setProfileStatus(null);
      setRawSources([]);
      setPersonaItems([]);
      setDeletedRawSources([]);
      setDeletedPersonaItems([]);
      setUncertainItems([]);
      setQuestionTargets([]);
      setSourceSegments([]);
      setQuestionAnswers({});
      setQuestionAnswerError(null);
      setQuestionAnswerNotice(null);
      setUncertainCorrections({});
      setUncertainNotes({});
      setUncertainActionError(null);
      setUncertainActionNotice(null);
      setSegmentError(null);
      setSegmentNotice(null);
    }
  }

  function handleCancelProfileEdit() {
    if (selectedProfile) {
      setEditName(selectedProfile.display_name);
      setEditRelationship(selectedProfile.relationship);
      setEditDescription(selectedProfile.description);
      setEditBoundaries(selectedProfile.boundaries.join("\n"));
    }
    setProfileEditError(null);
    setIsEditingProfile(false);
  }

  async function handleSaveProfileEdit() {
    if (!selectedProfileId) {
      return;
    }

    const displayName = editName.trim();
    if (!displayName) {
      setProfileEditError(t.profileNameRequired);
      return;
    }

    setIsSavingProfile(true);
    setProfileEditError(null);
    try {
      await updateProfile(selectedProfileId, {
        display_name: displayName,
        relationship: editRelationship,
        description: editDescription.trim(),
        boundaries: editBoundaries
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
      });
      await refreshProfileState(selectedProfileId);
      setIsEditingProfile(false);
    } catch (error) {
      setProfileEditError(error instanceof Error ? error.message : t.profileUpdateError);
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function handleDeleteProfile() {
    if (!selectedProfileId || !selectedProfile) {
      return;
    }
    const confirmed = window.confirm(t.deleteProfileConfirm.replace("{name}", selectedProfile.display_name));
    if (!confirmed) {
      return;
    }

    setIsDeletingProfile(true);
    setProfileEditError(null);
    try {
      await deleteProfile(selectedProfileId);
      setIsEditingProfile(false);
      await refreshProfilesAfterDelete();
    } catch (error) {
      setProfileEditError(error instanceof Error ? error.message : t.deleteProfileError);
    } finally {
      setIsDeletingProfile(false);
    }
  }

  async function handleReextract(sourceId: string) {
    if (!selectedProfileId) {
      return;
    }
    setReextractingSourceId(sourceId);
    setReextractError(null);
    try {
      await reextractRawSource(sourceId);
      await refreshProfileState(selectedProfileId);
    } catch (error) {
      setReextractError(error instanceof Error ? error.message : "重新提取失败");
    } finally {
      setReextractingSourceId(null);
    }
  }

  async function handleEnsureSegments(sourceId: string) {
    if (!selectedProfileId) {
      return;
    }
    setMutatingSegmentId(sourceId);
    setSegmentError(null);
    setSegmentNotice(null);
    try {
      const segments = await ensureRawSourceSegments(sourceId);
      await refreshProfileState(selectedProfileId);
      setActiveView("segments");
      setSegmentNotice(`已为这条资料建立 ${segments.length} 个片段记录，请继续确认归属。`);
    } catch (error) {
      setSegmentError(error instanceof Error ? error.message : "建立片段记录失败。");
    } finally {
      setMutatingSegmentId(null);
    }
  }

  async function handleBackfillSegments(scope: "profile" | "all") {
    if (scope === "profile" && !selectedProfileId) {
      return;
    }
    setIsBackfillingSegments(true);
    setSegmentError(null);
    setSegmentNotice(null);
    try {
      const result = await backfillSourceSegments({
        profileId: scope === "profile" ? selectedProfileId : null,
      });
      if (selectedProfileId) {
        await refreshProfileState(selectedProfileId);
      }
      setActiveView("segments");
      setSegmentNotice(
        `已补齐${scope === "profile" ? "当前人物" : "全部"}旧资料：新增 ${result.source_segments_created} 个片段、${result.extracted_segments_created} 个提取片段；仍有 ${result.pending_segment_count} 个片段需要人工确认。`,
      );
    } catch (error) {
      setSegmentError(error instanceof Error ? error.message : "批量补齐旧资料片段失败。");
    } finally {
      setIsBackfillingSegments(false);
    }
  }

  async function handleSegmentAction(segment: SourceSegmentSchema, action: SegmentAction) {
    if (!selectedProfileId) {
      return;
    }
    setMutatingSegmentId(segment.id);
    setSegmentError(null);
    setSegmentNotice(null);
    try {
      const source = rawSourcesById.get(segment.raw_source_id);
      await updateSourceSegment(segment.id, segmentActionPayload(action, segment));
      await refreshProfileState(selectedProfileId);
      if (action === "target_voice") {
        setSegmentNotice("已确认该片段属于当前人物，并允许作为声线参考用于 AI 声音生成。");
      } else if (action === "target_evidence") {
        setSegmentNotice("已确认该片段属于当前人物，可作为资料证据参与后续提取和复查。");
      } else if (action === "reject") {
        setSegmentNotice("已拒绝该片段，后续只保留审计记录，不作为当前人物证据。");
      } else {
        setSegmentNotice(`已把 ${sourceTitle(source)} 的片段标为${segmentTargetLabels[action]}，不会作为当前人物证据使用。`);
      }
    } catch (error) {
      setSegmentError(error instanceof Error ? error.message : "片段确认失败。");
    } finally {
      setMutatingSegmentId(null);
    }
  }

  async function handleBulkSegmentAction(action: SegmentAction) {
    if (!selectedProfileId || !selectedSegments.length) {
      return;
    }
    const targetSegments = selectedSegments;
    setBulkSegmentAction(action);
    setSegmentError(null);
    setSegmentNotice(null);
    try {
      for (const segment of targetSegments) {
        await updateSourceSegment(segment.id, segmentActionPayload(action, segment));
      }
      await refreshProfileState(selectedProfileId);
      setSelectedSegmentIds([]);
      setSegmentNotice(`已批量处理 ${targetSegments.length} 个片段；请继续检查剩余待确认项。`);
    } catch (error) {
      setSegmentError(error instanceof Error ? error.message : "批量确认片段失败。");
    } finally {
      setBulkSegmentAction(null);
    }
  }

  async function handleSubmitQuestionAnswer(target: QuestionTargetSchema) {
    if (!selectedProfileId) {
      return;
    }
    const answerText = (questionAnswers[target.id] ?? "").trim();
    if (!answerText) {
      setQuestionAnswerError("请先填写回答。");
      setQuestionAnswerNotice(null);
      return;
    }

    setSubmittingQuestionId(target.id);
    setQuestionAnswerError(null);
    setQuestionAnswerNotice(null);
    try {
      const result = await answerQuestionTarget(target.id, {
        answer_text: answerText,
        metadata: {
          submitted_from: "library_question_card",
        },
      });
      await refreshProfileState(selectedProfileId);
      if (result.classification_succeeded) {
        setQuestionAnswers((current) => {
          const next = { ...current };
          delete next[target.id];
          return next;
        });
        setQuestionAnswerNotice(
          `回答已保存为原始资料；提取成功，生成 ${result.persona_items.length} 条可用记忆；目标 ${getTargetLabel(
            target.target_group,
            target.target_library_key,
          )} 已解决。`,
        );
        return;
      }

      const reason =
        typeof result.diagnostics.model_call_reason === "string" && result.diagnostics.model_call_reason
          ? result.diagnostics.model_call_reason
          : "提取未成功";
      setQuestionAnswerError(`回答已保存为原始资料，但 ${reason}。问题会保持打开，不会生成本地保底记忆。`);
    } catch (error) {
      setQuestionAnswerError(error instanceof Error ? error.message : "回答提交失败");
    } finally {
      setSubmittingQuestionId(null);
    }
  }

  async function handleUncertainAction(item: UncertainItemSchema, action: ConfirmationOption) {
    if (!selectedProfileId) {
      return;
    }
    const correctedClaim = (uncertainCorrections[item.id] ?? "").trim();
    const note = (uncertainNotes[item.id] ?? "").trim();
    if (action === "correct" && !correctedClaim) {
      setUncertainActionError("选择纠正时需要先填写修正文案。");
      setUncertainActionNotice(null);
      return;
    }

    setMutatingUncertainId(item.id);
    setUncertainActionError(null);
    setUncertainActionNotice(null);
    try {
      const result = await actOnUncertainItem(item.id, {
        action,
        corrected_claim: correctedClaim || null,
        note: note || null,
        metadata: {
          submitted_from: "library_uncertain_item_card",
        },
      });
      await refreshProfileState(selectedProfileId);
      setUncertainCorrections((current) => {
        const next = { ...current };
        delete next[item.id];
        return next;
      });
      setUncertainNotes((current) => {
        const next = { ...current };
        delete next[item.id];
        return next;
      });
      const closedQuestions = result.question_targets.length;
      if (action === "keep" || action === "correct") {
        const rawSourceText = result.raw_source ? "已保存为确认资料" : "未生成新的确认资料";
        const personaItemText = result.classification_succeeded
          ? `提取成功，生成 ${result.persona_items.length} 条可用记忆`
          : "提取未成功，暂未写入稳定记忆";
        setUncertainActionNotice(
          `${uncertainActionLabels[action]}已记录；${rawSourceText}，${personaItemText}。关闭关联问题 ${closedQuestions} 个。策略：${uncertainActionResultText[action]}`,
        );
        return;
      }
      setUncertainActionNotice(
        `${uncertainActionLabels[action]}已记录；原始资料未删除，只更新使用策略，不生成稳定记忆。关闭关联问题 ${closedQuestions} 个。策略：${uncertainActionResultText[action]}`,
      );
    } catch (error) {
      setUncertainActionError(error instanceof Error ? error.message : "不确定项处理失败");
    } finally {
      setMutatingUncertainId(null);
    }
  }

  async function runTrashAction(itemId: string, action: () => Promise<unknown>) {
    if (!selectedProfileId) {
      return;
    }
    setMutatingTrashId(itemId);
    setTrashError(null);
    try {
      await action();
      await refreshProfileState(selectedProfileId);
    } catch (error) {
      setTrashError(error instanceof Error ? error.message : "操作失败");
    } finally {
      setMutatingTrashId(null);
    }
  }

  async function handleDeleteRawSource(source: RawSourceSchema) {
    const confirmed = window.confirm("删除这条原始资料并放入回收站？不会删除或隐藏可用记忆。");
    if (!confirmed) {
      return;
    }
    await runTrashAction(source.id, () => deleteRawSource(source.id));
  }

  async function handleDeletePersonaItem(item: PersonaItemSchema) {
    const confirmed = window.confirm("删除这条可用记忆并放入回收站？不会删除或隐藏原始资料。");
    if (!confirmed) {
      return;
    }
    await runTrashAction(item.id, () => deletePersonaItem(item.id));
  }

  async function handleRestoreRawSource(source: RawSourceSchema) {
    await runTrashAction(source.id, () => restoreRawSource(source.id));
  }

  async function handleRestorePersonaItem(item: PersonaItemSchema) {
    await runTrashAction(item.id, () => restorePersonaItem(item.id));
  }

  async function handlePurgeRawSource(source: RawSourceSchema) {
    const confirmed = window.confirm("彻底删除这条原始资料？这个操作不能恢复；关联片段和上传文件会一并清理，关联记忆会从可见与运行态隐藏。");
    if (!confirmed) {
      return;
    }
    await runTrashAction(source.id, () => purgeRawSource(source.id));
  }

  async function handlePurgePersonaItem(item: PersonaItemSchema) {
    const confirmed = window.confirm("彻底删除这条可用记忆？这个操作不能恢复，也不会删除原始资料。");
    if (!confirmed) {
      return;
    }
    await runTrashAction(item.id, () => purgePersonaItem(item.id));
  }

  return (
    <div className="flex h-[calc(100vh-6.5rem)] min-h-[620px] min-w-0 flex-col gap-3 overflow-hidden">
      <div className="rounded-md border bg-card px-4 py-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Badge className="border-primary/30 bg-primary/10 text-primary">{t.libraryBadge}</Badge>
              <h1 className="truncate text-base font-semibold">{t.libraryTitle}</h1>
            </div>
            <p className="mt-1 max-w-3xl truncate text-xs text-muted-foreground">
              在这里确认问题、查看可用记忆、复查原始资料，并处理回收站。
            </p>
          </div>
          <div className="grid grid-cols-4 gap-2 text-center text-xs">
            <div className="rounded-md border bg-background px-3 py-2">
              <div className="text-sm font-semibold">{rawSources.length}</div>
              <div className="text-muted-foreground">资料</div>
            </div>
            <div className="rounded-md border bg-background px-3 py-2">
              <div className="text-sm font-semibold">{visiblePersonaItems.length}</div>
              <div className="text-muted-foreground">记忆</div>
            </div>
            <div className="rounded-md border bg-background px-3 py-2">
              <div className="text-sm font-semibold">{openQuestionCount + openUncertainCount}</div>
              <div className="text-muted-foreground">待确认</div>
            </div>
            <div className="rounded-md border bg-background px-3 py-2">
              <div className="text-sm font-semibold">{deletedRawSources.length + deletedPersonaItems.length}</div>
              <div className="text-muted-foreground">回收站</div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid min-h-0 min-w-0 flex-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <Card className="flex min-h-0 flex-col overflow-hidden">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="size-5 text-primary" aria-hidden="true" />
              {t.libraryProfilesTitle}
            </CardTitle>
            <CardDescription>{t.libraryProfilesDescription}</CardDescription>
          </CardHeader>
          <CardContent className="min-h-0 flex-1 overflow-auto">
            {isLoadingProfiles ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                {t.libraryProfilesTitle}
              </div>
            ) : profileLoadError ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                {profileLoadError}
              </div>
            ) : profiles.length ? (
              <div className="space-y-2">
                {profiles.map((profile) => (
                  <Button
                    key={profile.id}
                    type="button"
                    variant={profile.id === selectedProfileId ? "default" : "outline"}
                    className="h-auto w-full justify-start whitespace-normal px-3 py-3 text-left"
                    onClick={() => {
                      setSelectedProfileId(profile.id);
                      setActiveProfileId(profile.id);
                    }}
                  >
                    <span className="grid gap-1">
                      <span>{profile.display_name}</span>
                      <span className="text-xs font-normal opacity-80">
                        {t[relationshipKeys[profile.relationship]]} / {formatDate(profile.updated_at)}
                      </span>
                    </span>
                  </Button>
                ))}
              </div>
            ) : (
              <div className="rounded-md border border-dashed p-5 text-sm leading-6 text-muted-foreground">
                {t.libraryEmptyProfiles}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="min-h-0 space-y-4 overflow-auto pr-0 lg:pr-1">
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="space-y-1.5">
                  <CardTitle>{selectedProfile?.display_name ?? t.libraryNoProfileSelected}</CardTitle>
                  <CardDescription>
                    {selectedProfile ? selectedProfile.description || t.libraryEvidenceDescription : t.libraryNoProfileSelected}
                  </CardDescription>
                </div>
                {selectedProfile ? (
                  <div className="flex flex-wrap gap-2">
                    {isEditingProfile ? (
                      <>
                        <Button type="button" variant="outline" size="sm" onClick={handleCancelProfileEdit} disabled={isSavingProfile}>
                          <X className="size-4" aria-hidden="true" />
                          {t.cancelEditProfile}
                        </Button>
                        <Button type="button" size="sm" onClick={handleSaveProfileEdit} disabled={isSavingProfile}>
                          {isSavingProfile ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Save className="size-4" aria-hidden="true" />}
                          {t.saveProfileButton}
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button type="button" variant="outline" size="sm" onClick={() => setIsEditingProfile(true)}>
                          <Pencil className="size-4" aria-hidden="true" />
                          {t.editProfileButton}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={handleDeleteProfile}
                          disabled={isDeletingProfile}
                          className="border-destructive/30 text-destructive hover:bg-destructive/10"
                        >
                          {isDeletingProfile ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Trash2 className="size-4" aria-hidden="true" />}
                          {t.deleteProfileButton}
                        </Button>
                      </>
                    )}
                  </div>
                ) : null}
              </div>
            </CardHeader>
            <CardContent>
              {profileEditError ? (
                <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {profileEditError}
                </div>
              ) : null}

              {!selectedProfile ? (
                <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                  {t.libraryNoProfileSelected}
                </div>
              ) : isEditingProfile ? (
                <div className="grid gap-4">
                  <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_180px]">
                    <div className="grid gap-2">
                      <Label htmlFor="edit-profile-name">{t.profileNameLabel}</Label>
                      <Input id="edit-profile-name" value={editName} onChange={(event) => setEditName(event.target.value)} />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="edit-profile-relationship">{t.relationshipLabel}</Label>
                      <select
                        id="edit-profile-relationship"
                        value={editRelationship}
                        onChange={(event) => setEditRelationship(event.target.value as RelationshipType)}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        {relationshipOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {t[option.labelKey]}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="edit-profile-description">{t.profileDescriptionLabel}</Label>
                    <Textarea
                      id="edit-profile-description"
                      value={editDescription}
                      onChange={(event) => setEditDescription(event.target.value)}
                      className="min-h-24 resize-y text-sm leading-6"
                      placeholder={t.profileDescriptionPlaceholder}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="edit-profile-boundaries">{t.profileBoundariesLabel}</Label>
                    <Textarea
                      id="edit-profile-boundaries"
                      value={editBoundaries}
                      onChange={(event) => setEditBoundaries(event.target.value)}
                      className="min-h-24 resize-y text-sm leading-6"
                      placeholder={t.profileBoundariesPlaceholder}
                    />
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {profileStatus ? (
                    <div className="rounded-md border bg-muted/30 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge>{profileStatus.stage_label}</Badge>
                        <Badge className="bg-background text-foreground">回复版本 {profileStatus.skill_version_count}</Badge>
                        <Badge className="bg-background text-foreground">
                          待确认 {profileStatus.open_question_count + profileStatus.open_uncertain_count}
                        </Badge>
                      </div>
                      <div className="mt-2 text-sm leading-6 text-muted-foreground">{profileStatus.next_action}</div>
                    </div>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <Link
                      href="/"
                      className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
                    >
                      <PlusCircle className="size-4" aria-hidden="true" />
                      添加资料
                    </Link>
                    <Link
                      href="/chat"
                      className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
                    >
                      <MessageCircle className="size-4" aria-hidden="true" />
                      去聊天
                    </Link>
                  </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs font-medium uppercase text-muted-foreground">{t.relationshipLabel}</div>
                    <div className="mt-1 text-sm font-medium">{t[relationshipKeys[selectedProfile.relationship]]}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs font-medium uppercase text-muted-foreground">资料数</div>
                    <div className="mt-1 text-sm font-medium">{detail?.raw_source_count ?? rawSources.length}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs font-medium uppercase text-muted-foreground">记忆条目</div>
                    <div className="mt-1 text-sm font-medium">{detail?.persona_item_count ?? visiblePersonaItems.length}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs font-medium uppercase text-muted-foreground">不确定项</div>
                    <div className="mt-1 text-sm font-medium">{detail?.uncertain_item_count ?? uncertainItems.length}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs font-medium uppercase text-muted-foreground">待回答问题</div>
                    <div className="mt-1 text-sm font-medium">{detail?.question_target_count ?? questionTargets.length}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs font-medium uppercase text-muted-foreground">待确认片段</div>
                    <div className="mt-1 text-sm font-medium">{pendingSegmentCount}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs font-medium uppercase text-muted-foreground">{t.createdAtLabel}</div>
                    <div className="mt-1 text-sm font-medium">{formatDate(selectedProfile.created_at)}</div>
                  </div>
                </div>
                </div>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-2 rounded-md border bg-card p-2 sm:grid-cols-5">
            {libraryViews.map((view) => {
              const count =
                view.value === "review"
                  ? openQuestionCount + openUncertainCount
                  : view.value === "segments"
                    ? pendingSegmentCount
                  : view.value === "items"
                    ? visiblePersonaItems.length
                    : view.value === "sources"
                      ? rawSources.length
                      : deletedRawSources.length + deletedPersonaItems.length;
              return (
                <button
                  key={view.value}
                  type="button"
                  onClick={() => setActiveView(view.value)}
                  className={`rounded-md border px-3 py-2 text-left transition-colors ${
                    activeView === view.value ? "border-primary bg-primary text-primary-foreground" : "bg-background hover:bg-muted"
                  }`}
                >
                  <span className="flex items-center justify-between gap-2 text-sm font-medium">
                    {view.label}
                    <span className="rounded border bg-background/70 px-2 py-0.5 text-xs text-foreground">{count}</span>
                  </span>
                  <span className="mt-1 block text-xs opacity-75">{view.description}</span>
                </button>
              );
            })}
          </div>

          {activeView === "review" ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <HelpCircle className="size-5 text-primary" aria-hidden="true" />
                待确认问题
              </CardTitle>
              <CardDescription>不确定线索先留在这里，由你回答、保留、纠正、降权、隐藏或遗忘。</CardDescription>
            </CardHeader>
            <CardContent>
              {uncertainActionError ? (
                <div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {uncertainActionError}
                </div>
              ) : null}
              {uncertainActionNotice ? (
                <div className="mb-3 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                  {uncertainActionNotice}
                </div>
              ) : null}
              {questionAnswerError ? (
                <div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {questionAnswerError}
                </div>
              ) : null}
              {questionAnswerNotice ? (
                <div className="mb-3 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                  {questionAnswerNotice}
                </div>
              ) : null}
              {isLoadingDetail ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Loading
                </div>
              ) : selectedProfile ? (
                uncertainItems.length || questionTargets.length ? (
                  <div className="space-y-5">
                    <div className="grid gap-2 sm:grid-cols-3">
                      <div className="rounded-md border bg-background p-3">
                        <div className="text-xs font-medium text-muted-foreground">待回答问题</div>
                        <div className="mt-1 text-lg font-semibold">{openQuestionCount}</div>
                        <div className="mt-1 text-xs leading-5 text-muted-foreground">回答后先保存原文证据</div>
                      </div>
                      <div className="rounded-md border bg-background p-3">
                        <div className="text-xs font-medium text-muted-foreground">待处理候选</div>
                        <div className="mt-1 text-lg font-semibold">{openUncertainCount}</div>
                        <div className="mt-1 text-xs leading-5 text-muted-foreground">可保留、纠正、降权、隐藏或遗忘</div>
                      </div>
                      <div className="rounded-md border bg-background p-3">
                        <div className="text-xs font-medium text-muted-foreground">写入边界</div>
                        <div className="mt-1 text-sm font-semibold">原文证据 -&gt; 可用记忆</div>
                        <div className="mt-1 text-xs leading-5 text-muted-foreground">提取成功才写入可用记忆</div>
                      </div>
                    </div>

                    {questionTargets.length ? (
                      <div className="space-y-3">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium">待回答问题</div>
                            <div className="text-xs leading-5 text-muted-foreground">问题会指向一个具体记忆类别，不会用固定问卷补齐。</div>
                          </div>
                          <Badge>{questionTargets.length}</Badge>
                        </div>
                        {questionTargets.map((target) => {
                          const matchedUncertain = uncertainItems.find((item) => item.id === target.uncertain_item_id) ?? null;
                          const reasonLabel = labelFromMap(questionReasonLabels, target.reason);
                          const reasonDescription = labelFromMap(questionReasonDescriptions, target.reason);
                          return (
                            <div key={target.id} className="rounded-md border bg-background p-4">
                              <div className="flex flex-wrap gap-2">
                                <Badge>{getTargetLabel(target.target_group, target.target_library_key)}</Badge>
                                <Badge className="bg-muted text-foreground">{reasonLabel}</Badge>
                                <Badge className="bg-muted text-foreground">优先级 {target.priority}</Badge>
                                <Badge className="bg-muted text-foreground">{labelFromMap(questionStatusLabels, target.status)}</Badge>
                              </div>
                              <div className="mt-3 grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_220px]">
                                <div className="min-w-0">
                                  <div className="text-sm font-medium leading-6">{target.question}</div>
                                  <div className="mt-1 text-xs leading-5 text-muted-foreground">{reasonDescription}</div>
                                </div>
                                <div className="rounded-md border bg-muted/40 px-3 py-2 text-xs leading-5">
                                  <div className="font-medium text-foreground">需要的证据</div>
                                  <div className="mt-1 text-muted-foreground">{getExpectedEvidenceText(target.expected_evidence_type)}</div>
                                </div>
                              </div>
                              {target.example_answer ? (
                                <div className="mt-2 rounded-md border bg-muted/30 px-3 py-2 text-xs leading-5 text-muted-foreground">
                                  <span className="font-medium text-foreground">示例方向：</span>
                                  {target.example_answer}
                                </div>
                              ) : null}
                              {matchedUncertain ? (
                                <div className="mt-3 rounded-md border-l-2 border-amber-400 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-950">
                                  <div className="font-medium">关联的不确定判断</div>
                                  <div className="mt-1">{matchedUncertain.claim}</div>
                                  <div className="mt-1 text-amber-900">{matchedUncertain.why_uncertain}</div>
                                </div>
                              ) : null}
                              <div className="mt-2 break-all text-xs leading-5 text-muted-foreground">
                                source: {target.source_id ?? "none"} / status: {labelFromMap(questionStatusLabels, target.status)} / {formatDate(target.created_at)}
                              </div>
                              <div className="mt-3 grid gap-2">
                                <Label htmlFor={`question-answer-${target.id}`} className="text-xs text-muted-foreground">
                                  你的确认回答
                                </Label>
                                <Textarea
                                  id={`question-answer-${target.id}`}
                                  value={questionAnswers[target.id] ?? ""}
                                  onChange={(event) =>
                                    setQuestionAnswers((current) => ({
                                      ...current,
                                      [target.id]: event.target.value,
                                    }))
                                  }
                                  placeholder="写具体细节、原话、场景或边界。"
                                  className="min-h-24"
                                  disabled={submittingQuestionId === target.id}
                                />
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <div className="text-xs leading-5 text-muted-foreground">
                                    提交结果：先保存原文证据；提取成功才写入可用记忆；失败则问题保持待回答。
                                  </div>
                                  <Button
                                    type="button"
                                    size="sm"
                                    onClick={() => {
                                      void handleSubmitQuestionAnswer(target);
                                    }}
                                    disabled={submittingQuestionId === target.id}
                                  >
                                    {submittingQuestionId === target.id ? (
                                      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                                    ) : (
                                      <Save className="size-4" aria-hidden="true" />
                                    )}
                                    提交回答
                                  </Button>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : null}

                    {uncertainItems.length ? (
                      <div className="space-y-3">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium">不确定项决策</div>
                            <div className="text-xs leading-5 text-muted-foreground">每个动作只改变使用策略；不会删除原数据。</div>
                          </div>
                          <Badge>{uncertainItems.length}</Badge>
                        </div>
                        {uncertainItems.map((item) => {
                          const riskLabel = labelFromMap(uncertainRiskLabels, item.risk_type);
                          const riskDescription = labelFromMap(uncertainRiskDescriptions, item.risk_type);
                          const usePolicy = getMetadataText(item.metadata, "use_policy");
                          return (
                            <div key={item.id} className="rounded-md border border-amber-200 bg-amber-50/40 p-4">
                              <div className="flex flex-wrap gap-2">
                                <Badge>{getTargetLabel(item.library_group, item.library_key)}</Badge>
                                <Badge className="bg-background text-foreground">{riskLabel}</Badge>
                                <Badge className="bg-background text-foreground">置信 {Math.round(item.confidence * 100)}%</Badge>
                                <Badge className="bg-background text-foreground">{labelFromMap(uncertainStatusLabels, item.status)}</Badge>
                              </div>
                              <div className="mt-3 text-sm font-medium leading-6">{item.claim}</div>
                              <div className="mt-2 grid gap-2 text-xs leading-5 text-muted-foreground md:grid-cols-2">
                                <div>
                                  <span className="font-medium text-foreground">为什么不确定：</span>
                                  {item.why_uncertain}
                                </div>
                                <div>
                                  <span className="font-medium text-foreground">风险类型：</span>
                                  {riskDescription}
                                </div>
                              </div>
                              {item.suggested_question ? (
                                <div className="mt-2 rounded-md border bg-background/80 px-3 py-2 text-xs leading-5 text-muted-foreground">
                                  <span className="font-medium text-foreground">可追问：</span>
                                  {item.suggested_question}
                                </div>
                              ) : null}
                              <div className="mt-3 grid gap-2 md:grid-cols-2">
                                <div className="grid gap-1">
                                  <Label htmlFor={`uncertain-correction-${item.id}`} className="text-xs text-muted-foreground">
                                    纠正文案
                                  </Label>
                                  <Textarea
                                    id={`uncertain-correction-${item.id}`}
                                    value={uncertainCorrections[item.id] ?? ""}
                                    onChange={(event) =>
                                      setUncertainCorrections((current) => ({
                                        ...current,
                                        [item.id]: event.target.value,
                                      }))
                                    }
                                    placeholder="选择纠正时填写用户确认后的说法"
                                    className="min-h-20 bg-background"
                                    disabled={mutatingUncertainId === item.id}
                                  />
                                </div>
                                <div className="grid gap-1">
                                  <Label htmlFor={`uncertain-note-${item.id}`} className="text-xs text-muted-foreground">
                                    处理备注
                                  </Label>
                                  <Textarea
                                    id={`uncertain-note-${item.id}`}
                                    value={uncertainNotes[item.id] ?? ""}
                                    onChange={(event) =>
                                      setUncertainNotes((current) => ({
                                        ...current,
                                        [item.id]: event.target.value,
                                      }))
                                    }
                                    placeholder="可选：为什么这样处理"
                                    className="min-h-20 bg-background"
                                    disabled={mutatingUncertainId === item.id}
                                  />
                                </div>
                              </div>
                              <div className="mt-3 grid gap-1 text-xs leading-5 text-muted-foreground sm:grid-cols-2">
                                {allUncertainActions.map((action) => (
                                  <div key={action}>
                                    <span className="font-medium text-foreground">{uncertainActionLabels[action]}：</span>
                                    {uncertainActionResultText[action]}
                                  </div>
                                ))}
                              </div>
                              <div className="mt-3 flex flex-wrap gap-2">
                                {allUncertainActions.map((action) => (
                                  <Button
                                    key={action}
                                    type="button"
                                    size="sm"
                                    variant={action === "forget" ? "destructive" : "outline"}
                                    onClick={() => {
                                      void handleUncertainAction(item, action);
                                    }}
                                    disabled={mutatingUncertainId === item.id}
                                    title={uncertainActionDescriptions[action]}
                                  >
                                    {mutatingUncertainId === item.id ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
                                    {uncertainActionLabels[action]}
                                  </Button>
                                ))}
                              </div>
                              <div className="mt-2 break-all text-xs leading-5 text-muted-foreground">
                                资料编号：{item.source_id ?? "none"} / 记忆编号：{item.persona_item_id ?? "none"} / 状态：{" "}
                                {labelFromMap(uncertainStatusLabels, item.status)}
                                {usePolicy ? ` / 策略：${usePolicy}` : ""} / {formatDate(item.created_at)}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                    当前没有待确认问题。这里不会用模板保底填充，只显示真实 coverage_warnings 生成的追问目标。
                  </div>
                )
              ) : (
                <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                  {t.libraryNoProfileSelected}
                </div>
              )}
            </CardContent>
          </Card>
          ) : null}

          {activeView === "segments" ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="size-5 text-primary" aria-hidden="true" />
                片段确认
              </CardTitle>
              <CardDescription>先确认资料片段属于谁，再决定它能否作为当前人物证据或声线参考。</CardDescription>
            </CardHeader>
            <CardContent>
              {segmentError ? (
                <div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {segmentError}
                </div>
              ) : null}
              {segmentNotice ? (
                <div className="mb-3 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                  {segmentNotice}
                </div>
              ) : null}
              {isLoadingDetail ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Loading
                </div>
              ) : selectedProfile ? (
                <div className="space-y-4">
                  <div className="grid gap-2 sm:grid-cols-4">
                    <div className="rounded-md border bg-background p-3">
                      <div className="text-xs font-medium text-muted-foreground">待确认片段</div>
                      <div className="mt-1 text-lg font-semibold">{pendingSegmentCount}</div>
                      <div className="mt-1 text-xs leading-5 text-muted-foreground">未确认前不当作当前人物证据</div>
                    </div>
                    <div className="rounded-md border bg-background p-3">
                      <div className="text-xs font-medium text-muted-foreground">当前人物片段</div>
                      <div className="mt-1 text-lg font-semibold">{confirmedTargetSegmentCount}</div>
                      <div className="mt-1 text-xs leading-5 text-muted-foreground">已由你确认归属</div>
                    </div>
                    <div className="rounded-md border bg-background p-3">
                      <div className="text-xs font-medium text-muted-foreground">可用声线</div>
                      <div className="mt-1 text-lg font-semibold">{voiceReadySegmentCount}</div>
                      <div className="mt-1 text-xs leading-5 text-muted-foreground">已确认归属和授权用途</div>
                    </div>
                    <div className="rounded-md border bg-background p-3">
                      <div className="text-xs font-medium text-muted-foreground">资料总片段</div>
                      <div className="mt-1 text-lg font-semibold">{sourceSegments.length}</div>
                      <div className="mt-1 text-xs leading-5 text-muted-foreground">旧资料会自动补默认片段</div>
                    </div>
                  </div>

                  <div className="rounded-md border bg-background p-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium">历史资料补齐</div>
                        <div className="mt-1 text-xs leading-5 text-muted-foreground">
                          只建立待确认片段，不会自动把旧资料标为当前人物，也不会自动授权声线。
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            void handleBackfillSegments("profile");
                          }}
                          disabled={isBackfillingSegments}
                        >
                          {isBackfillingSegments ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Database className="size-4" aria-hidden="true" />}
                          补齐当前人物旧资料
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            void handleBackfillSegments("all");
                          }}
                          disabled={isBackfillingSegments}
                        >
                          {isBackfillingSegments ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Database className="size-4" aria-hidden="true" />}
                          补齐全部旧资料
                        </Button>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-2 md:grid-cols-5">
                    {segmentFilterOptions.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => {
                          setSegmentFilter(option.value);
                          setSelectedSegmentIds([]);
                        }}
                        className={`rounded-md border px-3 py-2 text-left transition-colors ${
                          segmentFilter === option.value ? "border-primary bg-primary text-primary-foreground" : "bg-background hover:bg-muted"
                        }`}
                      >
                        <span className="flex items-center justify-between gap-2 text-sm font-medium">
                          {option.label}
                          <span className="rounded border bg-background/70 px-2 py-0.5 text-xs text-foreground">
                            {segmentFilterCounts[option.value]}
                          </span>
                        </span>
                        <span className="mt-1 block text-xs opacity-75">{option.description}</span>
                      </button>
                    ))}
                  </div>

                  <div className="rounded-md border bg-background p-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          className="size-4"
                          checked={filteredSourceSegments.length > 0 && selectedSegments.length === filteredSourceSegments.length}
                          onChange={(event) => {
                            setSelectedSegmentIds(event.target.checked ? filteredSourceSegments.map((segment) => segment.id) : []);
                          }}
                          aria-label="选择当前筛选片段"
                        />
                        <span>已选择 {selectedSegments.length} / 当前筛选 {filteredSourceSegments.length}</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => {
                            void handleBulkSegmentAction("target_evidence");
                          }}
                          disabled={!selectedSegments.length || bulkSegmentAction !== null}
                        >
                          {bulkSegmentAction === "target_evidence" ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <CheckSquare className="size-4" aria-hidden="true" />}
                          批量确认为证据
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            void handleBulkSegmentAction("target_voice");
                          }}
                          disabled={!selectedSegments.length || bulkSegmentAction !== null}
                        >
                          {bulkSegmentAction === "target_voice" ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <CheckSquare className="size-4" aria-hidden="true" />}
                          批量允许声线
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            void handleBulkSegmentAction("unknown");
                          }}
                          disabled={!selectedSegments.length || bulkSegmentAction !== null}
                        >
                          仍需复查
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="border-destructive/30 text-destructive hover:bg-destructive/10"
                          onClick={() => {
                            void handleBulkSegmentAction("reject");
                          }}
                          disabled={!selectedSegments.length || bulkSegmentAction !== null}
                        >
                          批量拒绝
                        </Button>
                      </div>
                    </div>
                  </div>

                  {sourceSegments.length ? (
                    <div className="space-y-3">
                      {filteredSourceSegments.length ? (
                      filteredSourceSegments.map((segment) => {
                          const source = rawSourcesById.get(segment.raw_source_id);
                          const isVoice = isVoiceReferenceSource(source) || segment.metadata.purpose === "voice_reference";
                          const isMutating = mutatingSegmentId === segment.id;
                          const isSelected = selectedSegmentIds.includes(segment.id);
                          return (
                            <div key={segment.id} className="rounded-md border bg-background p-4">
                              <div className="flex flex-wrap items-start justify-between gap-3">
                                <label className="flex items-center gap-2 text-sm">
                                  <input
                                    type="checkbox"
                                    className="size-4"
                                    checked={isSelected}
                                    onChange={(event) => {
                                      setSelectedSegmentIds((current) =>
                                        event.target.checked
                                          ? Array.from(new Set([...current, segment.id]))
                                          : current.filter((id) => id !== segment.id),
                                      );
                                    }}
                                    aria-label="选择片段"
                                  />
                                  选择
                                </label>
                                <div className="min-w-0 space-y-2">
                                  <div className="flex flex-wrap gap-2">
                                    <Badge>{segmentPurposeText(segment, source)}</Badge>
                                    <Badge className="bg-muted text-foreground">{sourceTitle(source)}</Badge>
                                    <Badge className="bg-muted text-foreground">
                                      {labelFromMap(segmentStatusLabels, segment.attribution_status)}
                                    </Badge>
                                    <Badge className="bg-muted text-foreground">{segmentTargetLabels[segment.target_person]}</Badge>
                                    {segment.consent_confirmed ? <Badge className="bg-emerald-50 text-emerald-900">已确认授权</Badge> : null}
                                  </div>
                                  <div className="break-all text-xs text-muted-foreground">
                                    片段：{segment.id} / 资料：{segment.raw_source_id} / {formatDate(segment.created_at)}
                                  </div>
                                </div>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    void handleEnsureSegments(segment.raw_source_id);
                                  }}
                                  disabled={isMutating}
                                >
                                  {isMutating ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RotateCcw className="size-4" aria-hidden="true" />}
                                  补齐片段
                                </Button>
                              </div>

                              <div className="mt-3 rounded-md bg-muted p-3 text-sm leading-6">
                                {segment.text_excerpt || "该片段没有可显示文本。音频/视频可先确认归属，转写和切段后续再补。"}
                              </div>

                              <div className="mt-2 rounded-md border border-dashed px-3 py-2 text-xs leading-5 text-muted-foreground">
                                {segmentEffectText(segment)}
                              </div>

                              <div className="mt-3 flex flex-wrap gap-2">
                                <Button
                                  type="button"
                                  size="sm"
                                  onClick={() => {
                                    void handleSegmentAction(segment, "target_evidence");
                                  }}
                                  disabled={isMutating}
                                >
                                  {isMutating ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Save className="size-4" aria-hidden="true" />}
                                  确认为当前人物证据
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant={isVoice ? "default" : "outline"}
                                  onClick={() => {
                                    void handleSegmentAction(segment, "target_voice");
                                  }}
                                  disabled={isMutating}
                                  title={isVoice ? "允许作为声线参考和声音生成来源" : "普通资料也可以确认归属，但声线用途通常应来自音频/视频参考"}
                                >
                                  {isMutating ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Save className="size-4" aria-hidden="true" />}
                                  确认并允许声线
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    void handleSegmentAction(segment, "user");
                                  }}
                                  disabled={isMutating}
                                >
                                  标为用户本人
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    void handleSegmentAction(segment, "other");
                                  }}
                                  disabled={isMutating}
                                >
                                  标为其他人
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    void handleSegmentAction(segment, "unknown");
                                  }}
                                  disabled={isMutating}
                                >
                                  仍需复查
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  className="border-destructive/30 text-destructive hover:bg-destructive/10"
                                  onClick={() => {
                                    void handleSegmentAction(segment, "reject");
                                  }}
                                  disabled={isMutating}
                                >
                                  拒绝片段
                                </Button>
                              </div>

                              <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                                {segment.permitted_uses.length ? (
                                  segment.permitted_uses.map((use) => (
                                    <span key={use} className="rounded border bg-muted px-2 py-1">
                                      {labelFromMap(segmentUseLabels, use)}
                                    </span>
                                  ))
                                ) : (
                                  <span className="rounded border bg-muted px-2 py-1">未授权用途</span>
                                )}
                              </div>
                            </div>
                          );
                        })
                      ) : (
                        <div className="rounded-md border border-dashed p-6 text-sm leading-6 text-muted-foreground">
                          当前筛选下没有片段。可以切换筛选，或先补齐旧资料片段。
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="rounded-md border border-dashed p-6 text-sm leading-6 text-muted-foreground">
                      还没有片段记录。去添加资料后，这里会显示待确认的片段；旧资料可在“原始资料”里点击补齐片段。
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                  {t.libraryNoProfileSelected}
                </div>
              )}
            </CardContent>
          </Card>
          ) : null}

          {activeView === "items" ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Layers3 className="size-5 text-primary" aria-hidden="true" />
                可用记忆库
              </CardTitle>
              <CardDescription>每条记忆都独立保存，并保留来源证据。</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoadingDetail ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Loading
                </div>
              ) : selectedProfile ? (
                <div className="space-y-3">
                  {!visiblePersonaItems.length ? (
                    <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                      {t.noPersonaAtomLibraries}
                    </div>
                  ) : null}
                  {groupedPersonaItems.map((group) => (
                    <details key={group.group} className="rounded-md border bg-background" open={group.items.length > 0}>
                      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
                        <span className="font-medium">{group.label}</span>
                        <Badge>{group.items.length}</Badge>
                      </summary>
                      <div className="space-y-3 border-t p-3">
                        {group.items.length ? (
                          group.items.map((item) => (
                            <div key={item.id} className="rounded-md border bg-muted/20 p-3">
                              <div className="flex flex-wrap items-start justify-between gap-2">
                                <div className="flex flex-wrap gap-2">
                                  <Badge>{item.library_key}</Badge>
                                  <Badge className="bg-background">{Math.round(item.confidence * 100)}%</Badge>
                                  <Badge className="bg-background">{item.status}</Badge>
                                  <Badge className="bg-background">{item.write_target}</Badge>
                                  {item.risk !== "none" ? <Badge className="bg-background">{item.risk}</Badge> : null}
                                </div>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  className="border-destructive/30 text-destructive hover:bg-destructive/10"
                                  onClick={() => {
                                    void handleDeletePersonaItem(item);
                                  }}
                                  disabled={mutatingTrashId === item.id}
                                  title="删除到回收站"
                                >
                                  {mutatingTrashId === item.id ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Trash2 className="size-4" aria-hidden="true" />}
                                  删除
                                </Button>
                              </div>
                              <div className="mt-3 text-sm font-medium leading-6">{item.signal}</div>
                              {item.prompt_snippet ? (
                                <div className="mt-2 rounded-md bg-background p-3 text-sm leading-6">{item.prompt_snippet}</div>
                              ) : null}
                              {item.evidence_quote ? (
                                <div className="mt-2 rounded-md border-l-2 border-primary/40 bg-background px-3 py-2 text-xs leading-5 text-muted-foreground">
                                  {item.evidence_quote}
                                </div>
                              ) : null}
                              <div className="mt-2 break-all text-xs leading-5 text-muted-foreground">
                                资料编号：{item.source_id ?? "none"} / {formatDate(item.created_at)}
                              </div>
                            </div>
                          ))
                        ) : (
                          <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">暂无条目</div>
                        )}
                      </div>
                    </details>
                  ))}
                </div>
              ) : (
                <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                  {t.libraryNoProfileSelected}
                </div>
              )}
            </CardContent>
          </Card>
          ) : null}

          {activeView === "sources" ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="size-5 text-primary" aria-hidden="true" />
                原始资料
              </CardTitle>
              <CardDescription>原始输入、转写文本和脱敏文本都在这里复查。</CardDescription>
            </CardHeader>
            <CardContent>
              {reextractError ? (
                <div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {reextractError}
                </div>
              ) : null}
              {trashError ? (
                <div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {trashError}
                </div>
              ) : null}
              {selectedProfile && rawSources.length ? (
                <div className="space-y-3">
                  {rawSources.map((source) => {
                    const originalQuestion = getRawSourceQuestion(source);
                    const segments = sourceSegmentsByRawSourceId.get(source.id) ?? [];
                    const pendingSegments = segments.filter(segmentNeedsReview).length;
                    return (
                    <div key={source.id} className="rounded-md border bg-background p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge>{source.source_type}</Badge>
                          <Badge className="bg-muted text-foreground">{formatDate(source.created_at)}</Badge>
                          <Badge className="bg-muted text-foreground">片段 {segments.length}</Badge>
                          {pendingSegments ? <Badge className="bg-amber-50 text-amber-900">待确认 {pendingSegments}</Badge> : null}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              if (segments.length) {
                                setActiveView("segments");
                                return;
                              }
                              void handleEnsureSegments(source.id);
                            }}
                            disabled={mutatingSegmentId === source.id}
                          >
                            {mutatingSegmentId === source.id ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Database className="size-4" aria-hidden="true" />}
                            {segments.length ? "确认片段" : "建立片段"}
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => handleReextract(source.id)}
                            disabled={reextractingSourceId === source.id || mutatingTrashId === source.id}
                          >
                            {reextractingSourceId === source.id ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Layers3 className="size-4" aria-hidden="true" />}
                            重新提取记忆
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="border-destructive/30 text-destructive hover:bg-destructive/10"
                            onClick={() => {
                              void handleDeleteRawSource(source);
                            }}
                            disabled={mutatingTrashId === source.id}
                            title="删除到回收站"
                          >
                            {mutatingTrashId === source.id ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Trash2 className="size-4" aria-hidden="true" />}
                            删除
                          </Button>
                        </div>
                      </div>
                      <div className="mt-2 break-all text-xs text-muted-foreground">{source.id}</div>
                      {originalQuestion ? (
                        <div className="mt-3 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-sm leading-6">
                          <div className="text-xs font-medium text-muted-foreground">原问题</div>
                          <div className="mt-1 whitespace-pre-wrap">{originalQuestion}</div>
                        </div>
                      ) : null}
                      <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 text-xs leading-5">
                        {source.pii_masked_text || source.extracted_text || source.original_text}
                      </pre>
                    </div>
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                  {selectedProfile ? t.libraryNoEvidence : t.libraryNoProfileSelected}
                </div>
              )}
            </CardContent>
          </Card>
          ) : null}

          {activeView === "trash" ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trash2 className="size-5 text-primary" aria-hidden="true" />
                回收站
              </CardTitle>
              <CardDescription>原始资料和可用记忆独立进入回收站；彻底删除原始资料会清理关联片段和上传文件，并隐藏关联记忆。</CardDescription>
            </CardHeader>
            <CardContent>
              {trashError ? (
                <div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {trashError}
                </div>
              ) : null}
              {!selectedProfile ? (
                <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                  {t.libraryNoProfileSelected}
                </div>
              ) : (
                <div className="grid min-w-0 gap-4 xl:grid-cols-2">
                  <div className="rounded-md border bg-background">
                    <div className="flex items-center justify-between border-b px-4 py-3">
                      <div className="font-medium">已删除原始资料</div>
                      <Badge>{deletedRawSources.length}</Badge>
                    </div>
                    <div className="space-y-3 p-3">
                      {deletedRawSources.length ? (
                        deletedRawSources.map((source) => (
                          <div key={source.id} className="rounded-md border bg-muted/20 p-3">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <div className="flex flex-wrap gap-2">
                                <Badge>{source.source_type}</Badge>
                                <Badge className="bg-background">{source.deleted_at ? formatDate(source.deleted_at) : "已删除"}</Badge>
                              </div>
                              <div className="flex flex-wrap gap-2">
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    void handleRestoreRawSource(source);
                                  }}
                                  disabled={mutatingTrashId === source.id}
                                >
                                  {mutatingTrashId === source.id ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RotateCcw className="size-4" aria-hidden="true" />}
                                  恢复
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  className="border-destructive/30 text-destructive hover:bg-destructive/10"
                                  onClick={() => {
                                    void handlePurgeRawSource(source);
                                  }}
                                  disabled={mutatingTrashId === source.id}
                                >
                                  <Trash2 className="size-4" aria-hidden="true" />
                                  彻底删除
                                </Button>
                              </div>
                            </div>
                            <div className="mt-2 break-all text-xs text-muted-foreground">{source.id}</div>
                            <pre className="mt-3 max-h-28 overflow-auto whitespace-pre-wrap rounded-md bg-background p-3 text-xs leading-5">
                              {source.pii_masked_text || source.extracted_text || source.original_text}
                            </pre>
                          </div>
                        ))
                      ) : (
                        <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">暂无已删除原始资料</div>
                      )}
                    </div>
                  </div>

                  <div className="rounded-md border bg-background">
                    <div className="flex items-center justify-between border-b px-4 py-3">
                      <div className="font-medium">已删除可用记忆</div>
                      <Badge>{deletedPersonaItems.length}</Badge>
                    </div>
                    <div className="space-y-3 p-3">
                      {deletedPersonaItems.length ? (
                        deletedPersonaItems.map((item) => (
                          <div key={item.id} className="rounded-md border bg-muted/20 p-3">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <div className="flex flex-wrap gap-2">
                                <Badge>{item.library_group}</Badge>
                                <Badge className="bg-background">{item.library_key}</Badge>
                                <Badge className="bg-background">{Math.round(item.confidence * 100)}%</Badge>
                              </div>
                              <div className="flex flex-wrap gap-2">
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    void handleRestorePersonaItem(item);
                                  }}
                                  disabled={mutatingTrashId === item.id}
                                >
                                  {mutatingTrashId === item.id ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RotateCcw className="size-4" aria-hidden="true" />}
                                  恢复
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  className="border-destructive/30 text-destructive hover:bg-destructive/10"
                                  onClick={() => {
                                    void handlePurgePersonaItem(item);
                                  }}
                                  disabled={mutatingTrashId === item.id}
                                >
                                  <Trash2 className="size-4" aria-hidden="true" />
                                  彻底删除
                                </Button>
                              </div>
                            </div>
                            <div className="mt-3 text-sm font-medium leading-6">{item.signal}</div>
                            <div className="mt-2 break-all text-xs leading-5 text-muted-foreground">
                              资料编号：{item.source_id ?? "none"} / 更新：{formatDate(item.updated_at)}
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">暂无已删除可用记忆</div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
