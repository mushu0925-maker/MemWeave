import { ClipboardCheck, FileText, PlugZap, type LucideIcon } from "lucide-react";

import type { RelationshipType, SourceType } from "@/lib/api";

type SourceOptionLabelKey = "sourceFile" | "sourceInterview" | "sourceExtension";
type RelationshipOptionLabelKey =
  | "relationshipFamily"
  | "relationshipFriend"
  | "relationshipPartner"
  | "relationshipMentor"
  | "relationshipSelf"
  | "relationshipOther";

export type CopyDocumentKind = "json" | "markdown" | "prompt" | "analysis";
export type QaAnswerKey = "relationshipMemory" | "speechDetails" | "careDetails" | "sceneDetails" | "boundaryDetails";

export const sourceOptions: Array<{ value: SourceType; labelKey: SourceOptionLabelKey; icon: LucideIcon }> = [
  { value: "file", labelKey: "sourceFile", icon: FileText },
  { value: "interview", labelKey: "sourceInterview", icon: ClipboardCheck },
  { value: "extension", labelKey: "sourceExtension", icon: PlugZap },
];

export const relationshipOptions: Array<{
  value: RelationshipType;
  labelKey: RelationshipOptionLabelKey;
}> = [
  { value: "family", labelKey: "relationshipFamily" },
  { value: "friend", labelKey: "relationshipFriend" },
  { value: "partner", labelKey: "relationshipPartner" },
  { value: "mentor", labelKey: "relationshipMentor" },
  { value: "self", labelKey: "relationshipSelf" },
  { value: "other", labelKey: "relationshipOther" },
];

export const starterContent =
  "聊天样本：妈妈常说“乖，先吃饭，别熬夜”。她看到我压力大时不会讲大道理，会先问我到家没有，然后说“慢慢来，身体最要紧”。\n\n关心案例：下雨时她会提醒我带伞，到家要报平安。她语气温柔，但有点爱唠叨。";

export const qaQuestionConfigs: Array<{
  key: QaAnswerKey;
  labelKey: "qaRelationshipLabel" | "qaSpeechLabel" | "qaCareLabel" | "qaSceneLabel" | "qaBoundaryLabel";
  placeholderKey:
    | "qaRelationshipPlaceholder"
    | "qaSpeechPlaceholder"
    | "qaCarePlaceholder"
    | "qaScenePlaceholder"
    | "qaBoundaryPlaceholder";
}> = [
  { key: "relationshipMemory", labelKey: "qaRelationshipLabel", placeholderKey: "qaRelationshipPlaceholder" },
  { key: "speechDetails", labelKey: "qaSpeechLabel", placeholderKey: "qaSpeechPlaceholder" },
  { key: "careDetails", labelKey: "qaCareLabel", placeholderKey: "qaCarePlaceholder" },
  { key: "sceneDetails", labelKey: "qaSceneLabel", placeholderKey: "qaScenePlaceholder" },
  { key: "boundaryDetails", labelKey: "qaBoundaryLabel", placeholderKey: "qaBoundaryPlaceholder" },
];

export const emptyQaAnswers: Record<QaAnswerKey, string> = {
  relationshipMemory: "",
  speechDetails: "",
  careDetails: "",
  sceneDetails: "",
  boundaryDetails: "",
};
