"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Library, Loader2, MessageSquareText, Save, UserRound } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ingestSkill,
  listProfiles,
  type IngestResponse,
  type ProfileSchema,
  type RelationshipType,
} from "@/lib/api";

const relationshipLabels: Record<RelationshipType, string> = {
  family: "亲人",
  friend: "朋友",
  partner: "伴侣",
  mentor: "师长",
  self: "自己",
  other: "其他",
};

const interviewPrompts = [
  {
    id: "portrait",
    title: "你心里的 TA 是什么样的人？",
    helper: "先用你的话描述，不需要客观完整。重点是你怎么记得 TA。",
    placeholder: "例如：他嘴硬但会照顾人，不太会直接表达，但遇到事情会默默兜底。",
  },
  {
    id: "scene",
    title: "有没有一个具体场景让你形成这种感觉？",
    helper: "尽量写时间、地点、当时发生了什么、TA 做了什么或说了什么。",
    placeholder: "例如：有一次我生病，他没有说很多安慰的话，但一直提醒我吃药，还帮我处理了别的事。",
  },
  {
    id: "care",
    title: "TA 通常怎么表达关心、保护、陪伴或责任？",
    helper: "把“对我好”拆成动作、话语、习惯或关系模式。",
    placeholder: "例如：会问我吃饭没有，到家要报平安，压力大时不会讲大道理，会先让我休息。",
  },
  {
    id: "conflict",
    title: "TA 让你受伤、失望或产生矛盾的时候是什么样？",
    helper: "可以写负面记忆。系统后续应支持保留、降权、隐藏或遗忘。",
    placeholder: "例如：吵架时他会沉默，不解释，但过一阵子会用行动缓和关系。",
  },
  {
    id: "language",
    title: "TA 有哪些原话、称呼、语气词或说话习惯？",
    helper: "原话越具体，后续语言风格越可靠。",
    placeholder: "例如：先吃饭，到家说一声，别熬夜。喜欢短句，不喜欢夸张煽情。",
  },
  {
    id: "boundary",
    title: "未来 AI 还原这个风格时绝对不能说什么？",
    helper: "写清楚不能编造、不能暗示、不能美化或不能触碰的边界。",
    placeholder: "例如：不能说自己真的复活了，不能编造没有发生过的承诺，不能替 TA 做现实决定。",
  },
] as const;

function buildInterviewContent(answers: Record<string, string>, profile: ProfileSchema | null) {
  const sections = interviewPrompts
    .map((prompt) => ({
      prompt,
      answer: (answers[prompt.id] ?? "").trim(),
    }))
    .filter((item) => item.answer);

  const header = [
    "访谈式记忆补全",
    "",
    `人物档案：${profile ? `${profile.display_name} / ${relationshipLabels[profile.relationship]}` : "未选择"}`,
    "访谈模式：AI 作为不了解 TA 的陌生访谈者，帮助用户描述自己心里的 TA。",
    "证据视角：这些回答应优先标记为 user_memory / user_feeling / user_perspective_portrait，不能直接当作客观事实。",
  ];

  return [
    ...header,
    "",
    ...sections.flatMap((item, index) => [
      `## ${index + 1}. ${item.prompt.title}`,
      item.answer,
      "",
    ]),
  ].join("\n");
}

export default function InterviewPage() {
  const [profiles, setProfiles] = useState<ProfileSchema[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? null,
    [profiles, selectedProfileId],
  );
  const answeredCount = useMemo(
    () => interviewPrompts.filter((prompt) => (answers[prompt.id] ?? "").trim()).length,
    [answers],
  );
  const previewContent = useMemo(
    () => buildInterviewContent(answers, selectedProfile),
    [answers, selectedProfile],
  );

  useEffect(() => {
    let isMounted = true;
    setIsLoadingProfiles(true);
    listProfiles()
      .then((items) => {
        if (!isMounted) {
          return;
        }
        setProfiles(items);
        setSelectedProfileId((current) =>
          current && items.some((profile) => profile.id === current) ? current : items[0]?.id ?? "",
        );
      })
      .catch((requestError) => {
        if (!isMounted) {
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "无法加载人物档案。");
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

  async function refreshProfiles() {
    const items = await listProfiles();
    setError(null);
    setProfiles(items);
    setSelectedProfileId((current) =>
      current && items.some((profile) => profile.id === current) ? current : items[0]?.id ?? "",
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);

    if (!selectedProfileId) {
      setError("请先选择一个人物档案。");
      return;
    }
    if (!answeredCount) {
      setError("至少回答一个访谈问题。");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await ingestSkill({
        source_type: "interview",
        raw_content: previewContent,
        profile_id: selectedProfileId,
        metadata: {
          submitted_from: "interview_page",
          interview_mode: "stranger_user_perspective",
          perspective_policy: "fact_memory_feeling_portrait_separated",
          answered_question_count: answeredCount,
          profile_name: selectedProfile?.display_name ?? null,
        },
      });
      setResult(response);
      await refreshProfiles();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "访谈提交失败。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(340px,0.95fr)]">
      <section className="space-y-6">
        <div className="space-y-2">
          <Badge className="border-primary/30 bg-primary/10 text-primary">用户视角访谈</Badge>
          <h1 className="max-w-3xl text-3xl font-semibold tracking-normal sm:text-4xl">
            通过问答补全你心里的那个人
          </h1>
          <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
            AI 不假装认识 TA。这里用陌生访谈者的方式，引导你把事实、记忆、感受和心中画像讲清楚；提交后会先保存为原始资料，再尝试提取为可用记忆。
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserRound className="size-5 text-primary" aria-hidden="true" />
              选择人物档案
            </CardTitle>
            <CardDescription>访谈回答必须归入一个 profile，方便后续追溯和重新提取。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-2">
              <Label htmlFor="interview-profile">人物档案</Label>
              <select
                id="interview-profile"
                value={selectedProfileId}
                onChange={(event) => setSelectedProfileId(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
                disabled={isLoadingProfiles || isSubmitting}
              >
                <option value="">{isLoadingProfiles ? "正在加载人物档案" : "请选择人物档案"}</option>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.display_name} / {relationshipLabels[profile.relationship]}
                  </option>
                ))}
              </select>
            </div>
            {!profiles.length && !isLoadingProfiles ? (
              <div className="rounded-md border border-dashed p-3 text-sm leading-6 text-muted-foreground">
                还没有人物档案。请先到仪表盘创建人物档案，再回来补充访谈记忆。
              </div>
            ) : null}
          </CardContent>
        </Card>

        <form className="space-y-4" onSubmit={handleSubmit}>
          {interviewPrompts.map((prompt, index) => (
            <Card key={prompt.id}>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <CardTitle className="text-base">
                      {index + 1}. {prompt.title}
                    </CardTitle>
                    <CardDescription>{prompt.helper}</CardDescription>
                  </div>
                  {(answers[prompt.id] ?? "").trim() ? (
                    <CheckCircle2 className="mt-1 size-5 text-primary" aria-hidden="true" />
                  ) : null}
                </div>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={answers[prompt.id] ?? ""}
                  onChange={(event) =>
                    setAnswers((current) => ({
                      ...current,
                      [prompt.id]: event.target.value,
                    }))
                  }
                  className="min-h-28 resize-y text-sm leading-6"
                  placeholder={prompt.placeholder}
                  disabled={isSubmitting}
                />
              </CardContent>
            </Card>
          ))}

          {error ? (
            <div className="whitespace-pre-wrap rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={isSubmitting || !selectedProfileId || !answeredCount}>
              {isSubmitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Save className="size-4" aria-hidden="true" />}
              保存访谈并提取记忆
            </Button>
            <div className="text-xs leading-5 text-muted-foreground">
              已回答 {answeredCount} / {interviewPrompts.length} 个问题
            </div>
          </div>
        </form>
      </section>

      <aside className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquareText className="size-5 text-primary" aria-hidden="true" />
              保存前预览
            </CardTitle>
            <CardDescription>这段文本会作为 `source_type=interview` 的 raw_source 保存。</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 text-xs leading-5">
              {answeredCount ? previewContent : "回答问题后，这里会生成即将保存的访谈原文。"}
            </pre>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Library className="size-5 text-primary" aria-hidden="true" />
              本次结果
            </CardTitle>
            <CardDescription>成功后可以到资料库查看原始资料和新生成的可用记忆。</CardDescription>
          </CardHeader>
          <CardContent>
            {result ? (
              <div className="space-y-3 text-sm leading-6">
                <div className="rounded-md border bg-primary/5 p-3">
                  <div className="font-medium text-primary">访谈已保存</div>
                  <div className="mt-1 break-all text-xs text-muted-foreground">
                    raw_source_id: {result.raw_source.id}
                  </div>
                </div>
                <div className="grid gap-2 sm:grid-cols-3">
                  <div className="rounded-md border p-3">
                    <div className="text-xs text-muted-foreground">可用记忆</div>
                    <div className="mt-1 text-lg font-semibold">{result.persona_items.length}</div>
                  </div>
                  <div className="rounded-md border p-3">
                    <div className="text-xs text-muted-foreground">不确定项</div>
                    <div className="mt-1 text-lg font-semibold">
                      {typeof result.diagnostics.persisted_uncertain_items === "number"
                        ? result.diagnostics.persisted_uncertain_items
                        : 0}
                    </div>
                  </div>
                  <div className="rounded-md border p-3">
                    <div className="text-xs text-muted-foreground">追问目标</div>
                    <div className="mt-1 text-lg font-semibold">
                      {typeof result.diagnostics.persisted_question_targets === "number"
                        ? result.diagnostics.persisted_question_targets
                        : 0}
                    </div>
                  </div>
                </div>
                <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
                  如果分类失败，原始访谈仍会被后端保留；可以之后在资料库重新提取。
                </div>
              </div>
            ) : (
              <div className="rounded-md border border-dashed p-6 text-sm leading-6 text-muted-foreground">
                提交访谈后，这里会显示保存结果和本次生成的可用记忆数量。
              </div>
            )}
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}
