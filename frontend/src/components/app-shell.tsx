"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Database,
  Library,
  Loader2,
  MessageCircle,
  Settings,
  ShieldCheck,
  Volume2,
} from "lucide-react";

import { useLanguage } from "@/components/language-provider";
import { Badge } from "@/components/ui/badge";
import {
  getAIConfig,
  getProfileStatus,
  getVoiceGenerationStatus,
  listProfiles,
  type AIConfigResponse,
  type ProfileSchema,
  type ProfileStatusResponse,
  type VoiceGenerationStatusResponse,
} from "@/lib/api";
import {
  readActiveProfileId,
  setActiveProfileId,
  WORKSPACE_PROFILE_EVENT,
  WORKSPACE_STATUS_EVENT,
} from "@/lib/workspace-state";

const navigation = [
  { href: "/", labelKey: "navDashboard", description: "添加资料", icon: BrainCircuit },
  { href: "/library", labelKey: "navLibrary", description: "确认/修正", icon: Library },
  { href: "/chat", labelKey: "navChat", description: "对话/声音", icon: MessageCircle },
  { href: "/settings", labelKey: "navSettings", description: "服务配置", icon: Settings },
  { href: "/login", labelKey: "navLogin", description: "账户", icon: ShieldCheck },
] as const;

function statusClass(ready: boolean) {
  return ready ? "border-primary/30 bg-primary/10 text-primary" : "border-amber-200 bg-amber-50 text-amber-900";
}

function serviceReadyText(ready: boolean) {
  return ready ? "可用" : "需配置";
}

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useLanguage();
  const pathname = usePathname();
  const [profiles, setProfiles] = useState<ProfileSchema[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [profileStatus, setProfileStatus] = useState<ProfileStatusResponse | null>(null);
  const [aiConfig, setAiConfig] = useState<AIConfigResponse | null>(null);
  const [voiceStatus, setVoiceStatus] = useState<VoiceGenerationStatusResponse | null>(null);
  const [isLoadingWorkspace, setIsLoadingWorkspace] = useState(true);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? null,
    [profiles, selectedProfileId],
  );
  const pendingCount = (profileStatus?.open_question_count ?? 0) + (profileStatus?.open_uncertain_count ?? 0);
  const modelReady = Boolean(aiConfig?.chat_enabled || aiConfig?.persona_enabled || aiConfig?.llm_enabled);
  const voiceReady = Boolean(voiceStatus?.enabled && voiceStatus.configured);

  const loadWorkspace = useCallback(async (preferredProfileId?: string | null) => {
    setWorkspaceError(null);
    setIsLoadingWorkspace(true);
    try {
      const [nextProfiles, nextConfig, nextVoiceStatus] = await Promise.all([
        listProfiles(),
        getAIConfig(),
        getVoiceGenerationStatus(),
      ]);
      const storedProfileId = preferredProfileId ?? readActiveProfileId();
      const nextProfileId =
        storedProfileId && nextProfiles.some((profile) => profile.id === storedProfileId)
          ? storedProfileId
          : nextProfiles[0]?.id ?? null;
      setProfiles(nextProfiles);
      setSelectedProfileId(nextProfileId);
      setAiConfig(nextConfig);
      setVoiceStatus(nextVoiceStatus);
      if (nextProfileId && readActiveProfileId() !== nextProfileId) {
        setActiveProfileId(nextProfileId);
      }
      setProfileStatus(nextProfileId ? await getProfileStatus(nextProfileId) : null);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "工作台状态加载失败。");
      setProfileStatus(null);
    } finally {
      setIsLoadingWorkspace(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspace();

    function handleProfileChange(event: Event) {
      const profileId = (event as CustomEvent<{ profileId?: string | null }>).detail?.profileId ?? readActiveProfileId();
      setSelectedProfileId(profileId ?? null);
      void loadWorkspace(profileId ?? null);
    }

    function handleStatusRefresh(event: Event) {
      const profileId = (event as CustomEvent<{ profileId?: string | null }>).detail?.profileId ?? readActiveProfileId();
      void loadWorkspace(profileId ?? null);
    }

    window.addEventListener(WORKSPACE_PROFILE_EVENT, handleProfileChange);
    window.addEventListener(WORKSPACE_STATUS_EVENT, handleStatusRefresh);
    window.addEventListener("focus", handleStatusRefresh);
    return () => {
      window.removeEventListener(WORKSPACE_PROFILE_EVENT, handleProfileChange);
      window.removeEventListener(WORKSPACE_STATUS_EVENT, handleStatusRefresh);
      window.removeEventListener("focus", handleStatusRefresh);
    };
  }, [loadWorkspace]);

  const nextAction = profileStatus?.next_action ?? (selectedProfile ? "添加资料或进入记忆库检查。" : "先创建或选择人物。");

  return (
    <div className="flex h-screen min-h-0 overflow-hidden bg-muted/40 text-foreground">
      <aside className="hidden w-64 shrink-0 border-r bg-card lg:flex lg:flex-col">
        <Link href="/" className="flex min-h-16 items-center gap-3 border-b px-4">
          <span className="flex size-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Database className="size-5" aria-hidden="true" />
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold">{t.appName}</span>
            <span className="block truncate text-xs text-muted-foreground">{t.appSubtitle}</span>
          </span>
        </Link>
        <nav className="min-h-0 flex-1 space-y-1 overflow-auto p-3">
          {navigation.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                <item.icon className="size-4" aria-hidden="true" />
                <span className="min-w-0">
                  <span className="block truncate">{t[item.labelKey]}</span>
                  <span className="block truncate text-[11px] font-normal opacity-75">{item.description}</span>
                </span>
              </Link>
            );
          })}
        </nav>
        <div className="space-y-3 border-t px-4 py-3 text-xs leading-5 text-muted-foreground">
          <div className="rounded-md border bg-background p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-foreground">当前人物</span>
              {isLoadingWorkspace ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> : null}
            </div>
            <div className="mt-1 truncate text-sm font-medium text-foreground">
              {selectedProfile?.display_name ?? "未选择"}
            </div>
            {profiles.length ? (
              <select
                value={selectedProfileId ?? ""}
                onChange={(event) => {
                  const nextProfileId = event.target.value || null;
                  setSelectedProfileId(nextProfileId);
                  setActiveProfileId(nextProfileId);
                }}
                className="mt-2 h-8 w-full rounded-md border border-input bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">未选择</option>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.display_name}
                  </option>
                ))}
              </select>
            ) : null}
            <div className="mt-1 max-h-10 overflow-hidden">{nextAction}</div>
            {profileStatus ? (
              <div className="mt-2 grid grid-cols-4 gap-1 text-center">
                <div className="rounded border bg-muted/30 px-1 py-1">
                  <div className="font-semibold text-foreground">{profileStatus.raw_source_count}</div>
                  <div>资料</div>
                </div>
                <div className="rounded border bg-muted/30 px-1 py-1">
                  <div className="font-semibold text-foreground">{profileStatus.persona_item_count}</div>
                  <div>记忆</div>
                </div>
                <div className="rounded border bg-muted/30 px-1 py-1">
                  <div className="font-semibold text-foreground">{pendingCount}</div>
                  <div>待审</div>
                </div>
                <div className="rounded border bg-muted/30 px-1 py-1">
                  <div className="font-semibold text-foreground">{profileStatus.skill_version_count}</div>
                  <div>版本</div>
                </div>
              </div>
            ) : null}
          </div>
          <div className="grid gap-2">
            <div className="flex items-center justify-between rounded-md border bg-background px-3 py-2">
              <span className="flex items-center gap-2">
                <CheckCircle2 className="size-3.5" aria-hidden="true" />
                模型
              </span>
              <Badge className={statusClass(modelReady)}>{serviceReadyText(modelReady)}</Badge>
            </div>
            <div className="flex items-center justify-between rounded-md border bg-background px-3 py-2">
              <span className="flex items-center gap-2">
                <Volume2 className="size-3.5" aria-hidden="true" />
                声音
              </span>
              <Badge className={statusClass(voiceReady)}>{serviceReadyText(voiceReady)}</Badge>
            </div>
          </div>
          {workspaceError ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-destructive">
              {workspaceError}
            </div>
          ) : null}
          <div>资料先保存为证据，再形成可追溯记忆；聊天和声音只使用已生成文本。</div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="shrink-0 border-b bg-card px-3 py-2 sm:px-4 lg:flex lg:min-h-14 lg:items-center lg:gap-3 lg:py-0">
          <Link href="/" className="flex items-center gap-2 lg:hidden">
            <span className="flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Database className="size-4" aria-hidden="true" />
            </span>
            <span className="text-sm font-semibold">{t.appName}</span>
          </Link>
          <div className="mt-2 min-w-0 lg:mt-0 lg:flex-1">
            <nav className="grid grid-cols-5 gap-1 lg:hidden">
              {navigation.map((item) => {
                const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex h-10 min-w-0 flex-col items-center justify-center gap-0.5 rounded-md px-1 text-[11px] font-medium leading-none ${
                      active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    }`}
                    aria-label={t[item.labelKey]}
                  >
                    <item.icon className="size-4 shrink-0" aria-hidden="true" />
                    <span className="max-w-full truncate">{t[item.labelKey]}</span>
                  </Link>
                );
              })}
            </nav>
            <div className="hidden truncate text-sm text-muted-foreground lg:block">
              {selectedProfile ? (
                <>
                  当前人物：<span className="font-medium text-foreground">{selectedProfile.display_name}</span>
                  {profileStatus ? ` · ${profileStatus.stage_label} · ${nextAction}` : ""}
                </>
              ) : (
                "选择人物，添加资料，检查记忆，再进入聊天或声音预览。"
              )}
            </div>
          </div>
          <div className="hidden shrink-0 items-center gap-2 lg:flex">
            <Badge className={statusClass(modelReady)}>模型 {serviceReadyText(modelReady)}</Badge>
            <Badge className={statusClass(voiceReady)}>声音 {serviceReadyText(voiceReady)}</Badge>
            {workspaceError ? (
              <Badge className="border-destructive/30 bg-destructive/10 text-destructive">
                <AlertTriangle className="size-3" aria-hidden="true" />
                状态异常
              </Badge>
            ) : null}
          </div>
        </header>
        <div className="border-b bg-card px-3 py-2 text-xs text-muted-foreground lg:hidden">
          <div className="flex min-w-0 items-center justify-between gap-2">
            <div className="min-w-0 truncate">
              当前人物：<span className="font-medium text-foreground">{selectedProfile?.display_name ?? "未选择"}</span>
            </div>
            <div className="flex shrink-0 gap-1">
              <Badge className={statusClass(modelReady)}>模型 {serviceReadyText(modelReady)}</Badge>
              <Badge className={statusClass(voiceReady)}>声音 {serviceReadyText(voiceReady)}</Badge>
            </div>
          </div>
          <div className="mt-1 truncate">{nextAction}</div>
        </div>
        <main className="min-h-0 flex-1 overflow-auto p-3 sm:p-4 lg:p-5">{children}</main>
      </div>
    </div>
  );
}
