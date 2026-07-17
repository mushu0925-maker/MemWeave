"use client";

import { useEffect, useState } from "react";
import { Activity, AlertTriangle, Check, ChevronDown, ChevronUp, Download, ExternalLink, Headphones, Languages, Loader2, Play, PlugZap, RefreshCw, Save, Server, Settings, ShieldCheck, Upload } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLanguage } from "@/components/language-provider";
import {
  discoverAIModels,
  downloadFullBackup,
  getAIConfig,
  getAIModelOptions,
  getSystemSelfCheck,
  getVoiceGenerationStatus,
  importBackup,
  inspectBackup,
  runAcceptanceE2E,
  testAIConnection,
  updateAIConfig,
  type AcceptanceCheckStatus,
  type AcceptanceRunResponse,
  type AIConnectionTestResponse,
  type AIConfigResponse,
  type AIConfigUpdateRequest,
  type AIModelDiscoveryFeature,
  type AIModelDiscoveryResponse,
  type AIModelOption,
  type AIModelOptionsResponse,
  type BackupImportPreview,
  type SystemCheckStatus,
  type SystemSelfCheckResponse,
  type VoiceGenerationStatusResponse,
} from "@/lib/api";
import { notifyWorkspaceStatusChanged } from "@/lib/workspace-state";

type TextFieldKey =
  | "llm_base_url"
  | "llm_proxy_url"
  | "llm_model"
  | "chat_base_url"
  | "chat_model"
  | "persona_base_url"
  | "persona_model"
  | "translate_model"
  | "evolution_model"
  | "vision_base_url"
  | "vision_model"
  | "asr_base_url"
  | "asr_model";

type SecretFieldKey = "chat_api_key" | "persona_api_key" | "vision_api_key" | "asr_api_key";

type CustomConfigSwitchKey =
  | "chat_use_custom_config"
  | "persona_use_custom_config"
  | "vision_use_custom_config"
  | "asr_use_custom_config";

const emptyConfig: AIConfigResponse = {
  llm_api_key_configured: false,
  llm_api_key_preview: null,
  llm_base_url: null,
  llm_proxy_url: null,
  llm_model: "",
  chat_use_custom_config: false,
  chat_api_key_configured: false,
  chat_api_key_preview: null,
  chat_base_url: null,
  chat_model: "",
  chat_effective_base_url: null,
  chat_effective_model: "",
  chat_enabled: false,
  persona_use_custom_config: false,
  persona_api_key_configured: false,
  persona_api_key_preview: null,
  persona_base_url: null,
  persona_model: "",
  persona_effective_base_url: null,
  persona_effective_model: "",
  persona_enabled: false,
  translate_model: "",
  evolution_model: "",
  vision_use_custom_config: true,
  vision_api_key_configured: false,
  vision_api_key_preview: null,
  vision_base_url: null,
  vision_model: "",
  vision_effective_base_url: null,
  vision_effective_model: "",
  asr_use_custom_config: true,
  asr_api_key_configured: false,
  asr_api_key_preview: null,
  asr_base_url: null,
  asr_model: "",
  asr_effective_base_url: null,
  asr_effective_model: "",
  enable_ai_classification: true,
  enable_vision_ocr: true,
  enable_asr: true,
  llm_enabled: false,
  vision_enabled: false,
  asr_enabled: false,
};

const emptyModelOptions: AIModelOptionsResponse = {
  text_models: [],
  vision_models: [],
  asr_models: [],
};

const modelDiscoveryFeatures: AIModelDiscoveryFeature[] = ["global", "chat", "classification", "vision", "asr"];

type ModelDiscoveries = Partial<Record<AIModelDiscoveryFeature, AIModelDiscoveryResponse>>;

const BACKEND_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const BACKEND_DOCS_URL = `${BACKEND_BASE_URL}/docs`;
const BACKEND_HEALTH_URL = `${BACKEND_BASE_URL}/health`;
const BACKEND_ADMIN_URL = `${BACKEND_BASE_URL}/admin`;

function mergeModelOptions(...optionGroups: AIModelOption[][]): AIModelOption[] {
  const seen = new Set<string>();
  const merged: AIModelOption[] = [];
  for (const options of optionGroups) {
    for (const option of options) {
      if (seen.has(option.id)) {
        continue;
      }
      seen.add(option.id);
      merged.push(option);
    }
  }
  return merged;
}

async function readModelDiscovery(feature: AIModelDiscoveryFeature): Promise<AIModelDiscoveryResponse> {
  try {
    return await discoverAIModels(feature);
  } catch {
    return {
      feature,
      status: "unavailable",
      source: "none",
      models: [],
      message: "",
    };
  }
}

function statusLabel(status: SystemCheckStatus | AcceptanceCheckStatus) {
  if (status === "pass") {
    return "通过";
  }
  if (status === "warning") {
    return "注意";
  }
  if (status === "fail") {
    return "失败";
  }
  if (status === "blocked") {
    return "阻塞";
  }
  return "跳过";
}

function statusClass(status: SystemCheckStatus | AcceptanceCheckStatus) {
  if (status === "pass") {
    return "border-primary/30 bg-primary/10 text-primary";
  }
  if (status === "warning") {
    return "border-amber-200 bg-amber-50 text-amber-900";
  }
  if (status === "fail" || status === "blocked") {
    return "border-destructive/30 bg-destructive/10 text-destructive";
  }
  return "border-muted bg-muted text-muted-foreground";
}

export default function SettingsPage() {
  const { language, setLanguage, t } = useLanguage();
  const [config, setConfig] = useState<AIConfigResponse>(emptyConfig);
  const [modelOptions, setModelOptions] = useState<AIModelOptionsResponse>(emptyModelOptions);
  const [modelDiscoveries, setModelDiscoveries] = useState<ModelDiscoveries>({});
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [functionApiKeys, setFunctionApiKeys] = useState<Record<SecretFieldKey, string>>({
    chat_api_key: "",
    persona_api_key: "",
    vision_api_key: "",
    asr_api_key: "",
  });
  const [clearFunctionApiKeys, setClearFunctionApiKeys] = useState<Record<SecretFieldKey, boolean>>({
    chat_api_key: false,
    persona_api_key: false,
    vision_api_key: false,
    asr_api_key: false,
  });
  const [showAdvanced, setShowAdvanced] = useState(true);
  const [voiceStatus, setVoiceStatus] = useState<VoiceGenerationStatusResponse | null>(null);
  const [systemCheck, setSystemCheck] = useState<SystemSelfCheckResponse | null>(null);
  const [selfCheckError, setSelfCheckError] = useState<string | null>(null);
  const [acceptanceResult, setAcceptanceResult] = useState<AcceptanceRunResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [discoveringFeatures, setDiscoveringFeatures] = useState<AIModelDiscoveryFeature[]>([]);
  const [isSelfChecking, setIsSelfChecking] = useState(true);
  const [isRunningAcceptance, setIsRunningAcceptance] = useState(false);
  const [testResult, setTestResult] = useState<AIConnectionTestResponse | null>(null);
  const [backupPreview, setBackupPreview] = useState<BackupImportPreview | null>(null);
  const [backupFileName, setBackupFileName] = useState("");
  const [backupConflictMode, setBackupConflictMode] = useState<"merge" | "import_as_new">("merge");
  const [isExportingBackup, setIsExportingBackup] = useState(false);
  const [isInspectingBackup, setIsInspectingBackup] = useState(false);
  const [isImportingBackup, setIsImportingBackup] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    Promise.all([getAIConfig(), getAIModelOptions(), getVoiceGenerationStatus()])
      .then(([nextConfig, nextOptions, nextVoiceStatus]) => {
        if (!isMounted) {
          return;
        }
        setConfig(nextConfig);
        setModelOptions(nextOptions);
        setVoiceStatus(nextVoiceStatus);
      })
      .catch((requestError) => {
        if (isMounted) {
          setError(requestError instanceof Error ? requestError.message : t.settingsLoadError);
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });
    getSystemSelfCheck()
      .then((nextSystemCheck) => {
        if (!isMounted) {
          return;
        }
        setSystemCheck(nextSystemCheck);
        setSelfCheckError(null);
      })
      .catch((requestError) => {
        if (isMounted) {
          setSelfCheckError(requestError instanceof Error ? requestError.message : "系统自检读取失败。");
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsSelfChecking(false);
        }
      });
    setDiscoveringFeatures(modelDiscoveryFeatures);
    Promise.all(modelDiscoveryFeatures.map(readModelDiscovery))
      .then((discoveries) => {
        if (!isMounted) {
          return;
        }
        setModelDiscoveries(
          Object.fromEntries(discoveries.map((discovery) => [discovery.feature, discovery])) as ModelDiscoveries,
        );
      })
      .finally(() => {
        if (isMounted) {
          setDiscoveringFeatures([]);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [t.settingsLoadError]);

  function updateTextField(key: TextFieldKey, value: string) {
    setConfig((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function updateSecretField(key: SecretFieldKey, value: string) {
    setFunctionApiKeys((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function updateClearSecretField(key: SecretFieldKey, value: boolean) {
    setClearFunctionApiKeys((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function updateCustomConfigSwitch(key: CustomConfigSwitchKey, value: boolean) {
    setConfig((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function statusBadge(enabled: boolean) {
    return (
      <Badge className={enabled ? "border-primary/30 bg-primary/10 text-primary" : "border-muted bg-muted text-muted-foreground"}>
        {enabled ? t.settingsEnabled : t.settingsDisabled}
      </Badge>
    );
  }

  function serviceCard(title: string, enabled: boolean, description: string, detail: string, icon: "server" | "audio") {
    const Icon = icon === "audio" ? Headphones : Server;
    return (
      <div className="rounded-md border bg-background p-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Icon className="size-4 text-primary" aria-hidden="true" />
              {title}
            </div>
            <div className="mt-1 text-xs leading-5 text-muted-foreground">{description}</div>
          </div>
          {statusBadge(enabled)}
        </div>
        <div className="mt-2 break-all rounded-md bg-muted/40 px-2 py-1 text-xs leading-5 text-muted-foreground">
          {detail}
        </div>
      </div>
    );
  }

  function discoveryFeatureLabel(feature: AIModelDiscoveryFeature) {
    const labels: Record<AIModelDiscoveryFeature, string> = {
      global: t.settingsModelDiscoveryGlobal,
      chat: t.settingsModelDiscoveryChat,
      classification: t.settingsModelDiscoveryClassification,
      vision: t.settingsModelDiscoveryVision,
      asr: t.settingsModelDiscoveryAsr,
    };
    return labels[feature];
  }

  function discoveryStatusText(discovery: AIModelDiscoveryResponse) {
    if (discovery.status === "available") {
      return `${t.settingsModelDiscoveryAvailable} (${discovery.models.length})`;
    }
    if (discovery.status === "empty") {
      return t.settingsModelDiscoveryEmpty;
    }
    if (discovery.status === "not_configured") {
      return t.settingsModelDiscoveryNotConfigured;
    }
    return t.settingsModelDiscoveryUnavailable;
  }

  function modelInput(
    key: TextFieldKey,
    label: string,
    options: AIModelOption[],
    feature: AIModelDiscoveryFeature,
    fallbackText?: string,
  ) {
    const value = String(config[key] ?? "");
    const discovery = modelDiscoveries[feature];
    const discoveredOptions = discovery?.models ?? [];
    const offlineOptions = options.filter(
      (option) => !discoveredOptions.some((discoveredOption) => discoveredOption.id === option.id),
    );
    const selectableOptions = mergeModelOptions(discoveredOptions, offlineOptions);
    const selectedOption = selectableOptions.find((option) => option.id === value);
    const isProviderValue = discoveredOptions.some((option) => option.id === value);
    const isDiscovering = discoveringFeatures.includes(feature);
    const note = isProviderValue
      ? t.settingsModelDiscoveredValueHint
      : selectedOption?.note ?? (value ? t.settingsModelCustomValueHint : fallbackText ?? t.settingsModelFallbackHint);

    return (
      <div className="grid gap-2">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor={`model-${key}`}>{label}</Label>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8 shrink-0"
            onClick={() => void handleDiscoverFeatureModels(feature)}
            disabled={isDiscovering}
            aria-label={`${t.settingsModelRefresh}: ${label}`}
            title={`${t.settingsModelRefresh}: ${label}`}
          >
            {isDiscovering ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />}
          </Button>
        </div>
        <Input
          id={`model-${key}`}
          value={value}
          onChange={(event) => updateTextField(key, event.target.value)}
          placeholder={key === "llm_model" ? t.settingsModelInputPlaceholder : t.settingsModelFallbackHint}
        />
        <select
          value=""
          onChange={(event) => {
            if (event.target.value) {
              updateTextField(key, event.target.value);
            }
          }}
          aria-label={`${label}: ${t.settingsModelSuggestionPlaceholder}`}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">
            {isDiscovering
              ? t.settingsModelDiscoveryLoading
              : discoveredOptions.length > 0
                ? `${t.settingsModelSuggestionPlaceholder} (${discoveredOptions.length})`
                : t.settingsModelSuggestionPlaceholder}
          </option>
          {discoveredOptions.length > 0 ? (
            <optgroup label={t.settingsModelProviderGroup}>
              {discoveredOptions.map((option) => (
                <option key={`provider-${option.id}`} value={option.id}>{option.label}</option>
              ))}
            </optgroup>
          ) : null}
          {offlineOptions.length > 0 ? (
            <optgroup label={t.settingsModelOfflineGroup}>
              {offlineOptions.map((option) => (
                <option key={`offline-${option.id}`} value={option.id}>{option.label}</option>
              ))}
            </optgroup>
          ) : null}
        </select>
        {isDiscovering ? (
          <p className="flex items-center gap-2 text-xs leading-5 text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            {t.settingsModelDiscoveryLoading}
          </p>
        ) : discovery ? (
          <p className="text-xs leading-5 text-muted-foreground">{discoveryStatusText(discovery)}</p>
        ) : null}
        <p className="text-xs leading-5 text-muted-foreground">{note}</p>
      </div>
    );
  }

  function functionEndpointCard({
    title,
    description,
    switchKey,
    secretKey,
    baseUrlKey,
    modelKey,
    feature,
    options,
    keyConfigured,
    keyPreview,
    effectiveBaseUrl,
    effectiveModel,
  }: {
    title: string;
    description: string;
    switchKey: CustomConfigSwitchKey;
    secretKey: SecretFieldKey;
    baseUrlKey: TextFieldKey;
    modelKey: TextFieldKey;
    feature: AIModelDiscoveryFeature;
    options: AIModelOption[];
    keyConfigured: boolean;
    keyPreview: string | null;
    effectiveBaseUrl: string | null;
    effectiveModel: string;
  }) {
    const enabled = Boolean(config[switchKey]);
    const secretValue = functionApiKeys[secretKey];
    const clearSecret = clearFunctionApiKeys[secretKey];
    return (
      <div className="grid gap-3 rounded-md border bg-background p-3">
        <label className="flex items-start justify-between gap-3 text-sm">
          <span className="min-w-0">
            <span className="block font-medium">{title}</span>
            <span className="mt-1 block text-xs leading-5 text-muted-foreground">{description}</span>
          </span>
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => updateCustomConfigSwitch(switchKey, event.target.checked)}
            className="mt-1 size-4 shrink-0"
          />
        </label>
        <div className="rounded-md bg-muted/40 px-3 py-2 text-xs leading-5 text-muted-foreground">
          实际使用：{effectiveBaseUrl || "全局默认接口"} / {effectiveModel || "全局默认模型"}
        </div>
        <div className="grid gap-2">
          <Label htmlFor={`secret-${secretKey}`}>API Key</Label>
          <Input
            id={`secret-${secretKey}`}
            type="password"
            value={secretValue}
            onChange={(event) => updateSecretField(secretKey, event.target.value)}
            placeholder={keyPreview ?? "留空则回退全局 API Key"}
            disabled={!enabled || clearSecret}
          />
          <div className="text-xs text-muted-foreground">
            {keyConfigured ? "已配置独立 Key" : "未配置独立 Key，留空回退全局 Key"}
            {keyPreview ? ` · ${keyPreview}` : ""}
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={clearSecret}
            onChange={(event) => updateClearSecretField(secretKey, event.target.checked)}
            disabled={!enabled}
            className="size-4"
          />
          清除这个功能的独立 API Key
        </label>
        <div className="grid gap-2">
          <Label htmlFor={`base-${baseUrlKey}`}>Base URL</Label>
          <Input
            id={`base-${baseUrlKey}`}
            value={String(config[baseUrlKey] ?? "")}
            onChange={(event) => updateTextField(baseUrlKey, event.target.value)}
            placeholder="留空则回退全局 Base URL"
            disabled={!enabled}
          />
        </div>
        {modelInput(modelKey, "Model", options, feature, "留空则回退全局模型")}
      </div>
    );
  }

  async function handleSaveSettings() {
    setIsSaving(true);
    setError(null);
    setMessage(null);
    setTestResult(null);

    const payload: AIConfigUpdateRequest = {
      llm_base_url: config.llm_base_url?.trim() || null,
      llm_proxy_url: config.llm_proxy_url?.trim() || null,
      llm_model: config.llm_model.trim() || null,
      chat_use_custom_config: config.chat_use_custom_config,
      chat_base_url: config.chat_base_url?.trim() || null,
      chat_model: config.chat_model.trim() || null,
      persona_use_custom_config: config.persona_use_custom_config,
      persona_base_url: config.persona_base_url?.trim() || null,
      persona_model: config.persona_model.trim() || null,
      translate_model: config.translate_model.trim() || null,
      evolution_model: config.evolution_model.trim() || null,
      vision_use_custom_config: config.vision_use_custom_config,
      vision_base_url: config.vision_base_url?.trim() || null,
      vision_model: config.vision_model.trim() || null,
      asr_use_custom_config: config.asr_use_custom_config,
      asr_base_url: config.asr_base_url?.trim() || null,
      asr_model: config.asr_model.trim() || null,
      enable_ai_classification: config.enable_ai_classification,
      enable_vision_ocr: config.enable_vision_ocr,
      enable_asr: config.enable_asr,
    };
    if (clearApiKey) {
      payload.llm_api_key = null;
    } else if (apiKey.trim()) {
      payload.llm_api_key = apiKey.trim();
    }
    (Object.keys(functionApiKeys) as SecretFieldKey[]).forEach((key) => {
      if (clearFunctionApiKeys[key]) {
        payload[key] = null;
        return;
      }
      const value = functionApiKeys[key].trim();
      if (value) {
        payload[key] = value;
      }
    });

    try {
      const nextConfig = await updateAIConfig(payload);
      setConfig(nextConfig);
      setVoiceStatus(await getVoiceGenerationStatus());
      await handleRefreshSystemCheck();
      setApiKey("");
      setClearApiKey(false);
      setFunctionApiKeys({
        chat_api_key: "",
        persona_api_key: "",
        vision_api_key: "",
        asr_api_key: "",
      });
      setClearFunctionApiKeys({
        chat_api_key: false,
        persona_api_key: false,
        vision_api_key: false,
        asr_api_key: false,
      });
      void handleDiscoverModels();
      setMessage(t.settingsSaved);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t.settingsSaveError);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleTestConnection() {
    setIsTesting(true);
    setError(null);
    setMessage(null);
    setTestResult(null);
    try {
      setTestResult(await testAIConnection());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t.settingsTestError);
    } finally {
      setIsTesting(false);
    }
  }

  async function handleDiscoverFeatureModels(feature: AIModelDiscoveryFeature) {
    setDiscoveringFeatures((current) => current.includes(feature) ? current : [...current, feature]);
    try {
      const discovery = await readModelDiscovery(feature);
      setModelDiscoveries((current) => ({ ...current, [feature]: discovery }));
    } finally {
      setDiscoveringFeatures((current) => current.filter((item) => item !== feature));
    }
  }

  async function handleDiscoverModels() {
    await Promise.all(modelDiscoveryFeatures.map(handleDiscoverFeatureModels));
  }

  async function handleRefreshSettings() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextConfig, nextOptions, nextVoiceStatus] = await Promise.all([
        getAIConfig(),
        getAIModelOptions(),
        getVoiceGenerationStatus(),
      ]);
      setConfig(nextConfig);
      setModelOptions(nextOptions);
      setVoiceStatus(nextVoiceStatus);
      await handleRefreshSystemCheck();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t.settingsLoadError);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleRefreshSystemCheck() {
    setIsSelfChecking(true);
    setSelfCheckError(null);
    try {
      setSystemCheck(await getSystemSelfCheck());
    } catch (requestError) {
      setSystemCheck(null);
      setSelfCheckError(requestError instanceof Error ? requestError.message : "系统自检读取失败。");
    } finally {
      setIsSelfChecking(false);
    }
  }

  async function handleRunAcceptance() {
    setIsRunningAcceptance(true);
    setError(null);
    setMessage(null);
    try {
      const result = await runAcceptanceE2E({
        create_isolated_profile: true,
        use_model_for_chat: false,
        updated_by: "settings-page",
      });
      setAcceptanceResult(result);
      await handleRefreshSystemCheck();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "严苛验收运行失败。");
    } finally {
      setIsRunningAcceptance(false);
    }
  }

  function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  async function handleExportBackup() {
    setIsExportingBackup(true);
    setError(null);
    setMessage(null);
    try {
      downloadBlob(await downloadFullBackup(), `memweave-backup-${new Date().toISOString().slice(0, 10)}.zip`);
      setMessage("完整备份已下载。备份不包含 API Key、凭据、模型权重或程序依赖。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "完整备份导出失败。");
    } finally {
      setIsExportingBackup(false);
    }
  }

  async function handleInspectBackup(file: File | null) {
    setBackupPreview(null);
    setBackupFileName(file?.name ?? "");
    if (!file) {
      return;
    }
    setIsInspectingBackup(true);
    setError(null);
    setMessage(null);
    try {
      setBackupPreview(await inspectBackup(file));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "备份预检失败。");
    } finally {
      setIsInspectingBackup(false);
    }
  }

  async function handleImportBackup() {
    if (!backupPreview) {
      return;
    }
    setIsImportingBackup(true);
    setError(null);
    setMessage(null);
    try {
      const result = await importBackup({
        import_token: backupPreview.import_token,
        profile_conflict_mode: backupConflictMode,
        global_data_mode: "keep_existing",
      });
      notifyWorkspaceStatusChanged();
      setBackupPreview(null);
      setBackupFileName("");
      setMessage(`已导入 ${result.imported_profile_ids.length} 个新人物，恢复 ${result.imported_attachment_count} 个附件。`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "备份导入失败。");
    } finally {
      setIsImportingBackup(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-6.5rem)] min-h-[620px] min-w-0 flex-col gap-3 overflow-hidden">
      <div className="rounded-md border bg-card px-4 py-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Badge className="border-primary/30 bg-primary/10 text-primary">{t.settingsBadge}</Badge>
              <h1 className="truncate text-base font-semibold">{t.settingsTitle}</h1>
            </div>
            <p className="mt-1 max-w-3xl truncate text-xs text-muted-foreground">{t.settingsDescription}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge className={systemCheck ? statusClass(systemCheck.overall_status) : "border-muted bg-muted text-muted-foreground"}>
              自检 {systemCheck ? statusLabel(systemCheck.overall_status) : "未读取"}
            </Badge>
            <Badge className={config.llm_enabled ? "border-primary/30 bg-primary/10 text-primary" : "border-amber-200 bg-amber-50 text-amber-900"}>
              模型 {config.llm_enabled ? "可用" : "需配置"}
            </Badge>
            <Badge className={voiceStatus?.enabled && voiceStatus.configured ? "border-primary/30 bg-primary/10 text-primary" : "border-amber-200 bg-amber-50 text-amber-900"}>
              声音 {voiceStatus?.enabled && voiceStatus.configured ? "可用" : "需配置"}
            </Badge>
            {voiceStatus && !voiceStatus.ffmpeg_available ? (
              <Badge className="border-amber-200 bg-amber-50 text-amber-900">
                <AlertTriangle className="size-3" aria-hidden="true" />
                视频抽音频不可用
              </Badge>
            ) : null}
          </div>
        </div>
      </div>

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      ) : null}
      {message ? (
        <div className="flex items-center gap-2 rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary">
          <Check className="size-4" aria-hidden="true" />
          {message}
        </div>
      ) : null}

      {isLoading ? (
        <Card>
          <CardContent className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            {t.settingsRuntimeStatusTitle}
          </CardContent>
        </Card>
      ) : (
        <div className="grid min-h-0 min-w-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <section className="min-h-0 space-y-4 overflow-auto pr-0 lg:pr-1">
            <Card>
              <CardHeader>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-1.5">
                    <CardTitle className="flex items-center gap-2">
                      <Download className="size-5 text-primary" aria-hidden="true" />
                      数据备份与恢复
                    </CardTitle>
                    <CardDescription>完整备份包含原始资料与派生数据；不会包含 API Key、凭据、模型权重或程序依赖。</CardDescription>
                  </div>
                  <Button type="button" size="sm" onClick={handleExportBackup} disabled={isExportingBackup}>
                    {isExportingBackup ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Download className="size-4" aria-hidden="true" />}
                    导出完整备份
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-3 rounded-md border bg-muted/30 p-3">
                  <div className="grid gap-2">
                    <Label htmlFor="backup-import-file">导入 ZIP 备份</Label>
                    <Input
                      id="backup-import-file"
                      type="file"
                      accept="application/zip,.zip"
                      onChange={(event) => void handleInspectBackup(event.target.files?.[0] ?? null)}
                      disabled={isInspectingBackup || isImportingBackup}
                    />
                    {backupFileName ? <div className="text-xs text-muted-foreground">已选择：{backupFileName}</div> : null}
                  </div>
                  {isInspectingBackup ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                      正在检查备份内容...
                    </div>
                  ) : null}
                  {backupPreview ? (
                    <div className="space-y-3 rounded-md border bg-background p-3">
                      <div className="grid gap-1 text-xs leading-5 text-muted-foreground sm:grid-cols-3">
                        <span>文档 {backupPreview.document_count}</span>
                        <span>附件 {backupPreview.attachment_count}</span>
                        <span>{backupPreview.profiles.length} 个人物</span>
                      </div>
                      <div className="space-y-2">
                        {backupPreview.profiles.map((profile) => (
                          <div key={profile.id} className="flex flex-col gap-1 rounded-md border px-3 py-2 text-xs sm:flex-row sm:items-center sm:justify-between">
                            <span className="font-medium">{profile.display_name}</span>
                            <span className={profile.conflicts_with_local ? "text-amber-900" : "text-muted-foreground"}>
                              {profile.conflicts_with_local ? "与本地人物 ID 冲突" : "可直接导入"}
                            </span>
                          </div>
                        ))}
                      </div>
                      {backupPreview.conflict_profile_ids.length > 0 ? (
                        <div className="grid gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
                          <div className="font-medium">发现同 ID 人物</div>
                          <label className="flex items-start gap-2">
                            <input type="radio" name="backup-conflict-mode" checked={backupConflictMode === "merge"} onChange={() => setBackupConflictMode("merge")} className="mt-0.5 size-4" />
                            <span>合并：保留本地人物资料，追加备份中的材料与派生记录。</span>
                          </label>
                          <label className="flex items-start gap-2">
                            <input type="radio" name="backup-conflict-mode" checked={backupConflictMode === "import_as_new"} onChange={() => setBackupConflictMode("import_as_new")} className="mt-0.5 size-4" />
                            <span>作为新人格导入：创建副本并重写关联 ID，不改动本地人物。</span>
                          </label>
                        </div>
                      ) : null}
                      {backupPreview.warnings.map((warning) => (
                        <div key={warning} className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950">{warning}</div>
                      ))}
                      <Button type="button" onClick={handleImportBackup} disabled={isImportingBackup}>
                        {isImportingBackup ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Upload className="size-4" aria-hidden="true" />}
                        {backupConflictMode === "import_as_new" ? "作为新人格导入" : "确认导入并合并"}
                      </Button>
                    </div>
                  ) : null}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-1.5">
                    <CardTitle className="flex items-center gap-2">
                      <ShieldCheck className="size-5 text-primary" aria-hidden="true" />
                      系统自检和核心验收
                    </CardTitle>
                    <CardDescription>先看真实可用状态，再跑一遍 raw source、A-M 库、聊天、Skill、片段层和声音依赖。</CardDescription>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" variant="outline" size="sm" onClick={handleRefreshSystemCheck} disabled={isSelfChecking}>
                      {isSelfChecking ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />}
                      刷新自检
                    </Button>
                    <Button type="button" size="sm" onClick={handleRunAcceptance} disabled={isRunningAcceptance}>
                      {isRunningAcceptance ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Play className="size-4" aria-hidden="true" />}
                      运行严苛验收
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {isSelfChecking ? (
                  <div className="flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-3 text-sm text-muted-foreground">
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                    正在读取系统自检...
                  </div>
                ) : null}
                {selfCheckError ? (
                  <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                    {selfCheckError}
                  </div>
                ) : null}
                {systemCheck ? (
                  <>
                    <div className="flex flex-col gap-3 rounded-md border bg-background p-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 text-sm font-medium">
                          <Activity className="size-4 text-primary" aria-hidden="true" />
                          总体状态：{statusLabel(systemCheck.overall_status)}
                        </div>
                        <div className="mt-1 text-xs leading-5 text-muted-foreground">
                          {systemCheck.app_name} · {systemCheck.environment} · {new Date(systemCheck.generated_at).toLocaleString()}
                        </div>
                      </div>
                      <Badge className={statusClass(systemCheck.overall_status)}>{statusLabel(systemCheck.overall_status)}</Badge>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      {systemCheck.checks.map((item) => (
                        <div key={item.key} className="rounded-md border bg-background p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="text-sm font-medium">{item.label}</div>
                              <div className="mt-1 text-xs leading-5 text-muted-foreground">{item.summary}</div>
                            </div>
                            <Badge className={statusClass(item.status)}>{statusLabel(item.status)}</Badge>
                          </div>
                          {item.detail ? <div className="mt-2 break-all rounded-md bg-muted/40 px-2 py-1 text-xs leading-5 text-muted-foreground">{item.detail}</div> : null}
                          {item.action ? <div className="mt-2 text-xs leading-5 text-amber-900">{item.action}</div> : null}
                        </div>
                      ))}
                    </div>
                  </>
                ) : null}
                {acceptanceResult ? (
                  <div className="rounded-md border bg-background p-3">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div className="text-sm font-medium">最近一次严苛验收</div>
                      <Badge className={statusClass(acceptanceResult.overall_status)}>{statusLabel(acceptanceResult.overall_status)}</Badge>
                    </div>
                    <div className="mt-1 text-xs leading-5 text-muted-foreground">
                      run_id：{acceptanceResult.run_id} · 算法：{acceptanceResult.algorithm_key} · 检查项：{acceptanceResult.summary.total ?? acceptanceResult.checks.length}
                    </div>
                    <div className="mt-3 space-y-2">
                      {acceptanceResult.checks
                        .filter((item) => item.status !== "pass")
                        .slice(0, 5)
                        .map((item) => (
                          <div key={item.key} className="rounded-md border bg-muted/30 px-3 py-2">
                            <div className="flex items-start justify-between gap-2">
                              <div className="text-xs font-medium">{item.name}</div>
                              <Badge className={statusClass(item.status)}>{statusLabel(item.status)}</Badge>
                            </div>
                            <div className="mt-1 text-xs leading-5 text-muted-foreground">{item.actual}</div>
                            {item.action_hint ? <div className="mt-1 text-xs leading-5 text-amber-900">{item.action_hint}</div> : null}
                          </div>
                        ))}
                      {acceptanceResult.checks.every((item) => item.status === "pass") ? (
                        <div className="rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-primary">
                          主链路验收通过。
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-1.5">
                    <CardTitle className="flex items-center gap-2">
                      <Server className="size-5 text-primary" aria-hidden="true" />
                      服务状态和下一步
                    </CardTitle>
                    <CardDescription>这里决定资料提取、聊天、音频转写和声线预览是否能真实运行。</CardDescription>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" variant="outline" size="sm" onClick={handleRefreshSettings} disabled={isLoading}>
                      {isLoading ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <PlugZap className="size-4" aria-hidden="true" />}
                      刷新状态
                    </Button>
                    <Button type="button" variant="outline" size="sm" onClick={handleTestConnection} disabled={isTesting}>
                      {isTesting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <PlugZap className="size-4" aria-hidden="true" />}
                      {isTesting ? t.settingsTestingConnection : t.settingsTestConnectionButton}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-3 md:grid-cols-2">
                  {serviceCard(
                    "大模型",
                    config.llm_enabled,
                    "用于资料提取、聊天回复和回复边界控制。",
                    config.llm_enabled ? `${config.llm_base_url || "默认接口"} / ${config.llm_model}` : "缺 API Key、接口地址或模型配置。",
                    "server",
                  )}
                  {serviceCard(
                    "视觉识别",
                    config.vision_enabled,
                    "用于图片/截图资料的文字和场景识别。",
                    config.vision_enabled ? config.vision_model || "使用默认视觉模型" : "关闭或缺少视觉模型配置。",
                    "server",
                  )}
                  {serviceCard(
                    "音频转写",
                    config.asr_enabled,
                    "用于音频资料转写，并生成声音特征候选线索。",
                    config.asr_enabled ? config.asr_model || "使用默认 ASR 模型" : "关闭或缺少 ASR 模型配置。",
                    "audio",
                  )}
                  {serviceCard(
                    "IndexTTS2 声音",
                    Boolean(voiceStatus?.enabled && voiceStatus.configured),
                    "只朗读已生成文本，不决定记忆事实或回复内容。",
                    voiceStatus
                      ? `${voiceStatus.enabled ? "声音开关已开启" : "声音开关未开启"} / 接口${voiceStatus.configured ? "已配置" : "未配置"} / 视频抽音频${voiceStatus.ffmpeg_available ? "可用" : "不可用"}`
                      : "声音服务状态未读取。",
                    "audio",
                  )}
                </div>
                {voiceStatus?.ffmpeg_error ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-950">
                    {voiceStatus.ffmpeg_error}
                  </div>
                ) : null}
                {testResult ? (
                  <div className={testResult.ok ? "rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-xs leading-5 text-primary" : "rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs leading-5 text-destructive"}>
                    <div>{testResult.ok ? t.settingsTestSuccess : t.settingsTestFailed}</div>
                    <div>状态：{testResult.status} · 服务：{testResult.provider} · 模型：{testResult.model}</div>
                    <div>{testResult.error ?? testResult.message}</div>
                  </div>
                ) : null}
                <div className="rounded-md border bg-background p-3">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <Server className="size-4 text-primary" aria-hidden="true" />
                        后端入口
                      </div>
                      <div className="mt-1 break-all text-xs leading-5 text-muted-foreground">
                        当前地址：{BACKEND_BASE_URL}
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <a
                        href={BACKEND_DOCS_URL}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-input bg-background px-3 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <ExternalLink className="size-4" aria-hidden="true" />
                        API 文档
                      </a>
                      <a
                        href={BACKEND_HEALTH_URL}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-input bg-background px-3 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <ExternalLink className="size-4" aria-hidden="true" />
                        健康检查
                      </a>
                      <a
                        href={BACKEND_ADMIN_URL}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-input bg-background px-3 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <ExternalLink className="size-4" aria-hidden="true" />
                        后端后台
                      </a>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Languages className="size-5 text-primary" aria-hidden="true" />
                  {t.settingsLanguageTitle}
                </CardTitle>
                <CardDescription>{t.settingsLanguageDescription}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="inline-flex rounded-md border bg-background p-1">
                  <Button
                    type="button"
                    variant={language === "zh" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setLanguage("zh")}
                  >
                    中文
                  </Button>
                  <Button
                    type="button"
                    variant={language === "en" ? "default" : "ghost"}
                    size="sm"
                    onClick={() => setLanguage("en")}
                  >
                    English
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-1.5">
                    <CardTitle className="flex items-center gap-2">
                      <Settings className="size-5 text-primary" aria-hidden="true" />
                      {t.settingsAdvancedTitle}
                    </CardTitle>
                    <CardDescription>{t.settingsAdvancedDescription}</CardDescription>
                  </div>
                  <Button type="button" variant="outline" size="sm" onClick={() => setShowAdvanced((current) => !current)}>
                    {showAdvanced ? <ChevronUp className="size-4" aria-hidden="true" /> : <ChevronDown className="size-4" aria-hidden="true" />}
                    {showAdvanced ? t.settingsHideAdvanced : t.settingsShowAdvanced}
                  </Button>
                </div>
              </CardHeader>
              {showAdvanced ? (
                <CardContent className="space-y-6">
                  <div className="grid gap-4 rounded-md border bg-muted/30 p-4">
                    <div>
                      <div className="font-medium">{t.settingsConnectionTitle}</div>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">{t.settingsConnectionDescription}</p>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="api-key">{t.settingsApiKeyLabel}</Label>
                      <Input
                        id="api-key"
                        type="password"
                        value={apiKey}
                        onChange={(event) => setApiKey(event.target.value)}
                        placeholder={config.llm_api_key_preview ?? t.settingsApiKeyPlaceholder}
                        disabled={clearApiKey}
                      />
                      <div className="text-xs text-muted-foreground">
                        {config.llm_api_key_configured ? t.settingsApiKeyConfigured : t.settingsApiKeyMissing}
                        {config.llm_api_key_preview ? ` · ${config.llm_api_key_preview}` : ""}
                      </div>
                    </div>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={clearApiKey}
                        onChange={(event) => setClearApiKey(event.target.checked)}
                        className="size-4"
                      />
                      {t.settingsClearApiKey}
                    </label>
                    <div className="grid gap-2">
                      <Label htmlFor="base-url">{t.settingsBaseUrlLabel}</Label>
                      <Input
                        id="base-url"
                        value={config.llm_base_url ?? ""}
                        onChange={(event) => updateTextField("llm_base_url", event.target.value)}
                        placeholder={t.settingsBaseUrlPlaceholder}
                      />
                      <p className="text-xs leading-5 text-muted-foreground">{t.settingsBaseUrlNote}</p>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="proxy-url">{t.settingsProxyUrlLabel}</Label>
                      <Input
                        id="proxy-url"
                        value={config.llm_proxy_url ?? ""}
                        onChange={(event) => updateTextField("llm_proxy_url", event.target.value)}
                        placeholder={t.settingsProxyUrlPlaceholder}
                      />
                      <p className="text-xs leading-5 text-muted-foreground">{t.settingsProxyUrlNote}</p>
                    </div>
                  </div>

                  <div className="grid gap-4 rounded-md border bg-muted/30 p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="font-medium">{t.settingsModelsTitle}</div>
                        <p className="mt-1 text-xs leading-5 text-muted-foreground">{t.settingsModelsDescription}</p>
                      </div>
                      <Button type="button" variant="outline" size="sm" onClick={handleDiscoverModels} disabled={discoveringFeatures.length > 0}>
                        {discoveringFeatures.length > 0 ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />}
                        {discoveringFeatures.length > 0 ? t.settingsModelDiscoveryLoading : t.settingsModelDiscoveryButton}
                      </Button>
                    </div>
                    <p className="text-xs leading-5 text-muted-foreground">{t.settingsModelDiscoveryHint}</p>
                    {modelDiscoveryFeatures.some((feature) => modelDiscoveries[feature]) ? (
                      <div className="grid gap-2 rounded-md border bg-background px-3 py-2 text-xs leading-5 text-muted-foreground">
                        {modelDiscoveryFeatures.map((feature) => {
                          const discovery = modelDiscoveries[feature];
                          return discovery ? <div key={feature}>{discoveryFeatureLabel(feature)}：{discoveryStatusText(discovery)}</div> : null;
                        })}
                      </div>
                    ) : null}
                    {modelInput("llm_model", t.settingsDefaultModelLabel, modelOptions.text_models, "global")}
                    {modelInput("translate_model", t.settingsTranslateModelLabel, modelOptions.text_models, "global")}
                    {modelInput("evolution_model", t.settingsEvolutionModelLabel, modelOptions.text_models, "global")}
                  </div>

                  <div className="grid gap-4 rounded-md border bg-muted/30 p-4">
                    <div>
                      <div className="font-medium">功能独立模型接入口</div>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">
                        打开某个功能的独立配置后，可以单独填写 API Key、Base URL 和 Model；留空的字段会回退到上面的全局默认配置。
                      </p>
                    </div>
                    <div className="grid gap-3 lg:grid-cols-2">
                      {functionEndpointCard({
                        title: "聊天回复",
                        description: "控制 Chat 页面真实调用模型时的接入口。",
                        switchKey: "chat_use_custom_config",
                        secretKey: "chat_api_key",
                        baseUrlKey: "chat_base_url",
                        modelKey: "chat_model",
                        feature: "chat",
                        options: modelOptions.text_models,
                        keyConfigured: config.chat_api_key_configured,
                        keyPreview: config.chat_api_key_preview,
                        effectiveBaseUrl: config.chat_effective_base_url,
                        effectiveModel: config.chat_effective_model,
                      })}
                      {functionEndpointCard({
                        title: "资料蒸馏/分类",
                        description: "控制 raw_source 写入 A-M 库时的结构化分类模型。",
                        switchKey: "persona_use_custom_config",
                        secretKey: "persona_api_key",
                        baseUrlKey: "persona_base_url",
                        modelKey: "persona_model",
                        feature: "classification",
                        options: modelOptions.text_models,
                        keyConfigured: config.persona_api_key_configured,
                        keyPreview: config.persona_api_key_preview,
                        effectiveBaseUrl: config.persona_effective_base_url,
                        effectiveModel: config.persona_effective_model,
                      })}
                      {functionEndpointCard({
                        title: "图片识别/OCR",
                        description: "控制图片、截图资料的视觉模型接入口。",
                        switchKey: "vision_use_custom_config",
                        secretKey: "vision_api_key",
                        baseUrlKey: "vision_base_url",
                        modelKey: "vision_model",
                        feature: "vision",
                        options: modelOptions.vision_models,
                        keyConfigured: config.vision_api_key_configured,
                        keyPreview: config.vision_api_key_preview,
                        effectiveBaseUrl: config.vision_effective_base_url,
                        effectiveModel: config.vision_effective_model,
                      })}
                      {functionEndpointCard({
                        title: "音频转写/ASR",
                        description: "控制音频资料转写和声音特征候选提取的模型接入口。",
                        switchKey: "asr_use_custom_config",
                        secretKey: "asr_api_key",
                        baseUrlKey: "asr_base_url",
                        modelKey: "asr_model",
                        feature: "asr",
                        options: modelOptions.asr_models,
                        keyConfigured: config.asr_api_key_configured,
                        keyPreview: config.asr_api_key_preview,
                        effectiveBaseUrl: config.asr_effective_base_url,
                        effectiveModel: config.asr_effective_model,
                      })}
                    </div>
                  </div>

                  <div className="grid gap-3 rounded-md border bg-muted/30 p-4">
                    <div>
                      <div className="font-medium">{t.settingsSwitchesTitle}</div>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">{t.settingsSwitchesDescription}</p>
                    </div>
                    {[
                      ["enable_ai_classification", t.settingsEnableClassification],
                      ["enable_vision_ocr", t.settingsEnableVision],
                      ["enable_asr", t.settingsEnableAsr],
                    ].map(([key, label]) => (
                      <label key={key} className="flex items-center justify-between gap-3 rounded-md border bg-background px-3 py-3 text-sm">
                        <span>{label}</span>
                        <input
                          type="checkbox"
                          checked={Boolean(config[key as keyof AIConfigResponse])}
                          onChange={(event) =>
                            setConfig((current) => ({
                              ...current,
                              [key]: event.target.checked,
                            }))
                          }
                          className="size-4"
                        />
                      </label>
                    ))}
                  </div>
                </CardContent>
              ) : null}
            </Card>
          </section>

          <aside className="min-h-0 space-y-4 overflow-auto">
            <Card>
              <CardHeader>
                <CardTitle>{t.settingsRuntimeStatusTitle}</CardTitle>
                <CardDescription>{t.settingsConnectionDescription}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  ["聊天回复", config.chat_enabled],
                  ["资料蒸馏/分类", config.persona_enabled],
                  [t.settingsVisionEnabled, config.vision_enabled],
                  [t.settingsAsrEnabled, config.asr_enabled],
                ].map(([label, enabled]) => (
                  <div key={label as string} className="flex items-center justify-between rounded-md border bg-background px-3 py-3 text-sm">
                    <span>{label as string}</span>
                    {statusBadge(Boolean(enabled))}
                  </div>
                ))}
              </CardContent>
            </Card>

            <Button type="button" className="w-full" onClick={handleSaveSettings} disabled={isSaving || !showAdvanced}>
              {isSaving ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Save className="size-4" aria-hidden="true" />}
              {t.settingsSaveButton}
            </Button>
          </aside>
        </div>
      )}
    </div>
  );
}
