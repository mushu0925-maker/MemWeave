"use client";

import { Check, Copy, Database, Download, FileJson, FileText, Layers3, Loader2, RefreshCw, Shield, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { IngestResponse, ProfileStatusResponse, SkillGenerationResponse, SkillVersion } from "@/lib/api";

import type { CopyDocumentKind } from "./config";

type DashboardResultPanelsProps = {
  result: IngestResponse | null;
  piiTotal: number;
  copiedKind: CopyDocumentKind | null;
  selectedProfileName: string | null;
  selectedProfileId: string | null;
  profileStatus: ProfileStatusResponse | null;
  skillResult: SkillGenerationResponse | null;
  skillError: string | null;
  skillCopiedKind: "markdown" | "json" | null;
  skillVersions: SkillVersion[];
  isGeneratingSkill: boolean;
  isSavingSkillVersion: boolean;
  deletingSkillVersionId: string | null;
  t: Record<string, string>;
  onCopyDocument: (kind: CopyDocumentKind) => void | Promise<void>;
  onDownloadIngestExport: () => void;
  onGenerateSkill: () => void | Promise<void>;
  onSaveSkillVersion: () => void | Promise<void>;
  onDeleteSkillVersion: (version: SkillVersion) => void | Promise<void>;
  onCopySkill: (kind: "markdown" | "json") => void | Promise<void>;
  onDownloadSkill: (kind: "markdown" | "json") => void;
};

export function DashboardResultPanels({
  result,
  piiTotal,
  copiedKind,
  selectedProfileName,
  selectedProfileId,
  profileStatus,
  skillResult,
  skillError,
  skillCopiedKind,
  skillVersions,
  isGeneratingSkill,
  isSavingSkillVersion,
  deletingSkillVersionId,
  t,
  onCopyDocument,
  onDownloadIngestExport,
  onGenerateSkill,
  onSaveSkillVersion,
  onDeleteSkillVersion,
  onCopySkill,
  onDownloadSkill,
}: DashboardResultPanelsProps) {
  const coverageWarnings = result?.diagnostics.coverage_warnings ?? [];
  const persistedUncertainItems = result?.diagnostics.persisted_uncertain_items ?? 0;
  const persistedQuestionTargets = result?.diagnostics.persisted_question_targets ?? 0;
  const voiceFeatureQuestionId = result?.diagnostics.voice_feature_question_target_id;
  const skillHasRuntimeSpeechPack = skillResult?.skill_markdown.includes("Runtime Speech Pack") ?? false;
  const skillHasSingleSourceCap =
    skillResult?.evidence_units.some((unit) => unit.cap_reason === "single_source_fact_requires_confirmation") ?? false;
  const selectedProfileLabel = selectedProfileName ?? selectedProfileId ?? "未选择 profile";

  return (
    <aside className="min-w-0 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers3 className="size-5 text-primary" aria-hidden="true" />
            流程状态
          </CardTitle>
          <CardDescription>这是独立状态总览，不改变蒸馏算法。</CardDescription>
        </CardHeader>
        <CardContent>
          {profileStatus ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{profileStatus.stage_label}</Badge>
                <Badge className="bg-background text-foreground">资料 {profileStatus.raw_source_count}</Badge>
                <Badge className="bg-background text-foreground">记忆 {profileStatus.persona_item_count}</Badge>
                <Badge className="bg-background text-foreground">待确认 {profileStatus.open_question_count + profileStatus.open_uncertain_count}</Badge>
                <Badge className="bg-background text-foreground">回复版本 {profileStatus.skill_version_count}</Badge>
              </div>
              <div className="rounded-md border bg-background px-3 py-2 text-sm leading-6 text-muted-foreground">
                {profileStatus.next_action}
              </div>
              {profileStatus.warnings.length ? (
                <div className="space-y-1 text-xs leading-5 text-amber-900">
                  {profileStatus.warnings.map((warning) => (
                    <div key={warning} className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1">
                      {warning}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
              选择 profile 后显示当前阶段和下一步。
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="size-5 text-primary" aria-hidden="true" />
            {t.privacyPassTitle}
          </CardTitle>
          <CardDescription>{t.privacyPassDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              ["email", t.piiEmail],
              ["phone", t.piiPhone],
              ["name", t.piiName],
            ].map(([key, label]) => (
              <div key={key} className="rounded-md border bg-background p-3">
                <div className="text-2xl font-semibold">{result?.pii_summary[key] ?? 0}</div>
                <div className="text-xs capitalize text-muted-foreground">{label}</div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            {piiTotal} {t.piiTotalSuffix}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="size-5 text-primary" aria-hidden="true" />
            原始资料
          </CardTitle>
          <CardDescription>原数据先保存，分类失败也不会丢。</CardDescription>
        </CardHeader>
        <CardContent>
          {result ? (
            <div className="space-y-3">
              <div className="rounded-md border bg-background p-3">
                <div className="text-xs font-medium uppercase text-muted-foreground">资料编号</div>
                <div className="mt-1 break-all text-sm font-medium">{result.raw_source.id}</div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-md border bg-background p-3">
                  <div className="text-xs font-medium uppercase text-muted-foreground">type</div>
                  <div className="mt-1 text-sm font-medium">{result.raw_source.source_type}</div>
                </div>
                <div className="rounded-md border bg-background p-3">
                  <div className="text-xs font-medium uppercase text-muted-foreground">hash</div>
                  <div className="mt-1 truncate text-sm font-medium">{result.raw_source.content_hash}</div>
                </div>
              </div>
              <pre className="max-h-52 overflow-auto rounded-md bg-muted p-3 text-xs leading-5">
                {result.sanitized_content}
              </pre>
            </div>
          ) : (
            <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
              {t.analysisEmpty}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-1.5">
              <CardTitle className="flex items-center gap-2">
                <FileText className="size-5 text-primary" aria-hidden="true" />
                回复版本
              </CardTitle>
              <CardDescription>从当前人物的可用记忆即时生成，可复制或下载检查。</CardDescription>
            </div>
            <Button
              type="button"
              size="sm"
              onClick={() => {
                void onGenerateSkill();
              }}
              disabled={!selectedProfileId || isGeneratingSkill}
              title={selectedProfileId ? "生成或刷新回复版本" : "请先选择人物"}
            >
              {isGeneratingSkill ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />}
              {skillResult ? "刷新回复版本" : "生成回复版本"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-md border bg-background p-3">
            <div className="text-xs font-medium uppercase text-muted-foreground">人物</div>
            <div className="mt-1 break-all text-sm font-medium">{selectedProfileLabel}</div>
          </div>

          {skillError ? (
            <div className="whitespace-pre-wrap rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {skillError}
            </div>
          ) : null}

          {skillResult ? (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-md border bg-background p-3">
                  <div className="text-xs font-medium uppercase text-muted-foreground">evidence</div>
                  <div className="mt-1 text-sm font-medium">{skillResult.evidence_units.length}</div>
                </div>
                <div className="rounded-md border bg-background p-3">
                  <div className="text-xs font-medium uppercase text-muted-foreground">audit</div>
                  <div className="mt-1 text-sm font-medium">{skillResult.audit_report.length}</div>
                </div>
                <div className="rounded-md border bg-background p-3">
                  <div className="text-xs font-medium uppercase text-muted-foreground">questions</div>
                  <div className="mt-1 text-sm font-medium">{skillResult.question_backlog.length}</div>
                </div>
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                <div className="flex items-center justify-between rounded-md border bg-background px-3 py-2 text-sm">
                  <span className="text-muted-foreground">运行时说话包</span>
                  <Badge className={skillHasRuntimeSpeechPack ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"}>
                    {skillHasRuntimeSpeechPack ? "已包含" : "未包含"}
                  </Badge>
                </div>
                <div className="flex items-center justify-between rounded-md border bg-background px-3 py-2 text-sm">
                  <span className="text-muted-foreground">单来源事实硬门</span>
                  <Badge className={skillHasSingleSourceCap ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"}>
                    {skillHasSingleSourceCap ? "已命中" : "未命中"}
                  </Badge>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    void onSaveSkillVersion();
                  }}
                  disabled={!skillResult || isSavingSkillVersion}
                >
                  {isSavingSkillVersion ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Database className="size-4" aria-hidden="true" />}
                  保存版本
                </Button>
                {([
                  ["markdown", "Markdown"],
                  ["json", "JSON"],
                ] as const).map(([kind, label]) => (
                  <Button
                    key={`copy-${kind}`}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      void onCopySkill(kind);
                    }}
                  >
                    {skillCopiedKind === kind ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
                    {skillCopiedKind === kind ? "已复制" : `复制 ${label}`}
                  </Button>
                ))}
                {([
                  ["markdown", "MD", FileText],
                  ["json", "JSON", FileJson],
                ] as const).map(([kind, label, Icon]) => (
                  <Button
                    key={`download-${kind}`}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => onDownloadSkill(kind)}
                  >
                    <Icon className="size-4" aria-hidden="true" />
                    下载 {label}
                  </Button>
                ))}
              </div>

              <pre className="max-h-72 overflow-auto rounded-md bg-muted p-3 text-xs leading-5">
                {skillResult.skill_markdown}
              </pre>
            </div>
          ) : (
            <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
              选择人物后点击“生成回复版本”，这里会显示可检查的内容、审计数量和可下载文件。
            </div>
          )}

          {skillVersions.length ? (
            <div className="mt-4 space-y-2">
              <div className="text-sm font-medium">已保存回复版本</div>
              {skillVersions.slice(0, 5).map((version) => (
                <div key={version.id} className="rounded-md border bg-background p-3 text-xs leading-5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-medium text-foreground">{version.title}</div>
                    <div className="flex items-center gap-2">
                      <Badge className="bg-muted text-foreground">{new Date(version.created_at).toLocaleString()}</Badge>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-7 border-destructive/30 px-2 text-xs text-destructive hover:bg-destructive/10"
                        disabled={deletingSkillVersionId === version.id}
                        onClick={() => {
                          void onDeleteSkillVersion(version);
                        }}
                      >
                        {deletingSkillVersionId === version.id ? (
                          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                        ) : (
                          <Trash2 className="size-3.5" aria-hidden="true" />
                        )}
                        删除
                      </Button>
                    </div>
                  </div>
                  <div className="mt-1 text-muted-foreground">
                    依据 {version.evidence_unit_count} · 待审 {version.audit_count} · 问题 {version.question_backlog_count}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-1.5">
              <CardTitle className="flex items-center gap-2">
                <Layers3 className="size-5 text-primary" aria-hidden="true" />
                本次提取的可用记忆
              </CardTitle>
              <CardDescription>这些条目来自原始资料，后续聊天和回复版本都以它们为依据。</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              {([
                ["json", t.copyJson],
                ["markdown", t.copyMarkdown],
                ["prompt", t.copyPrompt],
                ["analysis", t.copyAnalysis],
              ] as const).map(([kind, label]) => (
                <Button
                  key={kind}
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    void onCopyDocument(kind);
                  }}
                  disabled={!result}
                  title={result ? label : t.exportSkillDisabled}
                >
                  {copiedKind === kind ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
                  {copiedKind === kind ? t.copied : label}
                </Button>
              ))}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onDownloadIngestExport}
                disabled={!result}
                title={result ? t.exportSkill : t.exportSkillDisabled}
              >
                <Download className="size-4" aria-hidden="true" />
                导出 ingest JSON
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {result ? (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-md border bg-background p-3">
                  <div className="text-xs font-medium uppercase text-muted-foreground">saved</div>
                  <div className="mt-1 text-sm font-medium">{result.persona_items.length}</div>
                </div>
                <div className="rounded-md border bg-background p-3">
                  <div className="text-xs font-medium uppercase text-muted-foreground">classified</div>
                  <div className="mt-1 text-sm font-medium">{result.persona_library_classification?.items.length ?? 0}</div>
                </div>
                <div className="rounded-md border bg-background p-3">
                  <div className="text-xs font-medium uppercase text-muted-foreground">routing</div>
                  <div className="mt-1 text-sm font-medium">{result.routing_key}</div>
                </div>
              </div>
              {coverageWarnings.length ? (
                <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                  <div className="font-medium">有 {coverageWarnings.length} 个维度需要后续确认</div>
                  <div className="mt-1 text-xs leading-5">
                    已保存 AI 实际抽取的条目，未生成本地保底。缺失维度会作为后续针对性问答依据。
                    {typeof persistedQuestionTargets === "number" && persistedQuestionTargets > 0
                      ? ` 已持久化 ${persistedUncertainItems} 个不确定项、${persistedQuestionTargets} 个追问目标。`
                      : ""}
                  </div>
                  <div className="mt-2 space-y-1">
                    {coverageWarnings.slice(0, 4).map((warning) => (
                      <div key={`${warning.library_group}-${warning.category}`} className="text-xs leading-5">
                        <span className="font-medium">{warning.library_group} {warning.label}</span>
                        <span className="text-amber-800">：{warning.suggested_question}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {voiceFeatureQuestionId ? (
                <div className="rounded-md border border-primary/25 bg-primary/5 p-3 text-sm leading-6 text-foreground">
                  <div className="font-medium">语音特征候选已进入待确认</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    目标：M / {result.diagnostics.voice_feature_target_library_key ?? "voice_speech_features"}。这些内容只用于描述说话方式，不是声音克隆、声线复刻或冒充指令。
                  </div>
                  <div className="mt-1 break-all text-xs text-muted-foreground">question_target_id: {voiceFeatureQuestionId}</div>
                </div>
              ) : null}
              {result.persona_items.length ? (
                <div className="space-y-2">
                  {result.persona_items.slice(0, 12).map((item) => (
                    <div key={item.id} className="rounded-md border bg-background p-3">
                      <div className="flex flex-wrap gap-2">
                        <Badge>{item.library_group}</Badge>
                        <Badge className="bg-muted text-foreground">{item.library_key}</Badge>
                        <Badge className="bg-muted text-foreground">{Math.round(item.confidence * 100)}%</Badge>
                        <Badge className="bg-muted text-foreground">{item.status}</Badge>
                      </div>
                      <div className="mt-2 text-sm font-medium leading-6">{item.signal}</div>
                      <div className="mt-1 text-xs leading-5 text-muted-foreground">{item.prompt_snippet}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                  提取成功但没有写入可用记忆。通常是因为没有选择人物。
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
              {t.skillEmpty}
            </div>
          )}
        </CardContent>
      </Card>
    </aside>
  );
}
