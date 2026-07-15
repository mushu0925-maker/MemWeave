from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    acceptance,
    chat,
    config,
    distillation_plugins,
    feature_policies,
    history_isolation,
    ingest,
    integrity,
    library_plugins,
    memory_completion,
    mcp,
    monitoring,
    persona_items,
    profiles,
    quality_validation,
    raw_sources,
    runtime_gate,
    runtime_modules,
    source_segments,
    skills,
    storage,
    system,
    uncertainty,
    voice,
)
from app.core.config import get_settings
from app.services.local_database import LocalDatabaseCorruptionError


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, prefix=settings.api_v1_prefix)
app.include_router(config.router, prefix=settings.api_v1_prefix)
app.include_router(profiles.router, prefix=settings.api_v1_prefix)
app.include_router(raw_sources.router, prefix=settings.api_v1_prefix)
app.include_router(source_segments.router, prefix=settings.api_v1_prefix)
app.include_router(runtime_gate.router, prefix=settings.api_v1_prefix)
app.include_router(runtime_modules.router, prefix=settings.api_v1_prefix)
app.include_router(history_isolation.router, prefix=settings.api_v1_prefix)
app.include_router(persona_items.router, prefix=settings.api_v1_prefix)
app.include_router(uncertainty.router, prefix=settings.api_v1_prefix)
app.include_router(voice.router, prefix=settings.api_v1_prefix)
app.include_router(chat.router, prefix=settings.api_v1_prefix)
app.include_router(skills.router, prefix=settings.api_v1_prefix)
app.include_router(integrity.router, prefix=settings.api_v1_prefix)
app.include_router(mcp.router, prefix=settings.api_v1_prefix)
app.include_router(monitoring.router, prefix=settings.api_v1_prefix)
app.include_router(storage.router, prefix=settings.api_v1_prefix)
app.include_router(system.router, prefix=settings.api_v1_prefix)
app.include_router(feature_policies.router, prefix=settings.api_v1_prefix)
app.include_router(distillation_plugins.router, prefix=settings.api_v1_prefix)
app.include_router(library_plugins.router, prefix=settings.api_v1_prefix)
app.include_router(acceptance.router, prefix=settings.api_v1_prefix)
app.include_router(memory_completion.router, prefix=settings.api_v1_prefix)
app.include_router(quality_validation.router, prefix=settings.api_v1_prefix)


@app.exception_handler(LocalDatabaseCorruptionError)
def handle_local_database_corruption(
    _request: Request,
    exc: LocalDatabaseCorruptionError,
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "message": "本地 JSON 数据文件解析失败，后端已停止使用默认空数据以避免覆盖真实数据。",
                "filename": exc.filename,
                "path": str(exc.path),
                "error": exc.message,
            }
        },
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.get("/monitoring", response_class=HTMLResponse)
def monitoring_dashboard_shortcut() -> HTMLResponse:
    return monitoring.monitoring_dashboard()


@app.get("/admin", response_class=HTMLResponse)
def backend_admin_shortcut() -> HTMLResponse:
    return HTMLResponse(_BACKEND_ADMIN_HTML)


_BACKEND_ADMIN_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>后端管理后台</title>
  <style>
    :root { --bg:#f6f7f9; --panel:#fff; --text:#172033; --muted:#667085; --border:#d0d7e2; --blue:#2563eb; --red:#b91c1c; }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    header { background:var(--panel); border-bottom:1px solid var(--border); padding:18px 24px; display:flex; justify-content:space-between; gap:16px; align-items:center; }
    h1 { margin:0; font-size:20px; }
    main { max-width:1440px; margin:0 auto; padding:20px 24px 42px; }
    a { color:var(--blue); text-decoration:none; }
    .toolbar { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(360px,1fr)); gap:14px; }
    .panel { background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:14px; }
    .head { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
    .title { font-weight:700; font-size:15px; }
    .muted { color:var(--muted); }
    .small { font-size:12px; }
    code, pre { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:12px; }
    pre { background:#f8fafc; border:1px solid var(--border); border-radius:6px; padding:8px; white-space:pre-wrap; overflow:auto; max-height:160px; }
    input, select, textarea, button { border:1px solid var(--border); border-radius:6px; background:#fff; color:var(--text); font:inherit; }
    input, select { height:34px; padding:0 9px; }
    textarea { width:100%; min-height:82px; padding:8px; }
    button { height:34px; padding:0 12px; cursor:pointer; }
    button.primary { background:var(--blue); border-color:var(--blue); color:#fff; }
    .status { display:inline-flex; min-width:72px; justify-content:center; align-items:center; height:24px; padding:0 8px; border-radius:999px; border:1px solid var(--border); background:#f8fafc; font-size:12px; }
    .ok { color:#047857; border-color:#a7f3d0; background:#ecfdf5; }
    .warning { color:#b45309; border-color:#fcd34d; background:#fffbeb; }
    .blocked, .fail, .blocker { color:#b91c1c; border-color:#fecaca; background:#fff1f2; }
    .disabled, .unknown, .audit { color:#475467; border-color:#d0d5dd; background:#f2f4f7; }
    .row { display:grid; grid-template-columns:130px 1fr; gap:8px; align-items:center; margin-top:8px; }
    .checks { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:8px; margin-top:8px; }
    .check { display:flex; gap:6px; align-items:center; min-width:0; }
    .check input { width:16px; height:16px; }
    .danger { color:var(--red); }
    .section-title { margin:22px 0 10px; font-size:16px; }
    .two-col { display:grid; grid-template-columns:repeat(auto-fit,minmax(420px,1fr)); gap:14px; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>后端管理后台</h1>
      <div class="muted small">功能策略、算法 key、严格程度和写入规则都在后端控制。</div>
    </div>
    <div class="toolbar">
      <button class="primary" onclick="loadPolicies()">刷新策略</button>
      <button onclick="loadPlugins()">刷新插件</button>
      <a href="/monitoring">监控面板</a>
      <a href="/docs" target="_blank">OpenAPI</a>
    </div>
  </header>
  <main>
    <h2 class="section-title">系统总览</h2>
    <div class="grid">
      <section class="panel">
        <div class="head">
          <div>
            <div class="title">服务状态</div>
            <div class="muted small">后端健康、当前 profile 和主要维护入口。</div>
          </div>
          <span id="healthStatus" class="status unknown">unknown</span>
        </div>
        <div class="row"><label>profile_id</label><input id="globalProfileId" placeholder="可选；用于监控/验收/日志筛选" /></div>
        <div class="toolbar" style="margin-top:10px">
          <button onclick="loadOverview()">刷新总览</button>
          <button onclick="syncProfileTargets()">同步到所有表单</button>
        </div>
        <pre id="healthResult">未加载</pre>
      </section>
      <section class="panel">
        <div class="head">
          <div>
            <div class="title">数据完整性</div>
            <div class="muted small">扫描 raw/persona/uncertain/question/chat/skill 证据链。</div>
          </div>
          <span id="integrityStatus" class="status unknown">unknown</span>
        </div>
        <div class="toolbar" style="margin-top:10px">
          <button onclick="loadIntegrity()">扫描</button>
          <button onclick="repairIntegrity()">修复</button>
        </div>
        <pre id="integrityResult">未扫描</pre>
      </section>
      <section class="panel">
        <div class="head">
          <div>
            <div class="title">自动验收</div>
            <div class="muted small">严格检查证据链、确认流、运行态和监控归因。</div>
          </div>
          <span id="acceptanceStatus" class="status unknown">unknown</span>
        </div>
        <div class="toolbar" style="margin-top:10px">
          <button onclick="runAcceptanceFromOverview()">运行自动验收</button>
        </div>
        <pre id="acceptanceSummary">未运行</pre>
      </section>
      <section class="panel">
        <div class="head">
          <div>
            <div class="title">监控与日志</div>
            <div class="muted small">展示真实分母、样本 ID、归因和近期 AI/Skill 事件。</div>
          </div>
          <span id="monitoringStatus" class="status unknown">unknown</span>
        </div>
        <div class="row"><label>event_type</label><select id="adminEventType">
          <option value="">全部</option>
          <option value="distillation">AI 蒸馏</option>
          <option value="chat_skill_usage">AI 使用 Skill 回复</option>
          <option value="skill_generation">Skill 生成</option>
          <option value="confirmation">确认/纠错</option>
          <option value="acceptance">验收</option>
        </select></div>
        <div class="row"><label>status</label><select id="adminEventStatus">
          <option value="">全部</option>
          <option value="success">success</option>
          <option value="failed">failed</option>
          <option value="skipped">skipped</option>
          <option value="blocked">blocked</option>
          <option value="local">local</option>
        </select></div>
        <div class="row"><label>workflow</label><input id="adminEventWorkflow" placeholder="可选精确匹配" /></div>
        <div class="row"><label>subject_id</label><input id="adminEventSubjectId" placeholder="可选精确匹配" /></div>
        <div class="toolbar" style="margin-top:10px">
          <button onclick="loadMonitoring()">刷新监控</button>
          <button onclick="loadAdminEvents()">刷新日志</button>
        </div>
        <pre id="monitoringResult">未加载</pre>
        <pre id="eventsResult">未加载</pre>
      </section>
    </div>
    <h2 class="section-title">运行态准入</h2>
    <section class="panel">
      <div class="head">
        <div>
          <div class="title">Runtime Gate</div>
          <div class="muted small">控制 persona_items 是否允许进入 Skill 输入和聊天检索；规则独立于蒸馏算法，可后端热调整。</div>
        </div>
        <span id="runtimeGateStatus" class="status unknown">unknown</span>
      </div>
      <div class="row"><label>enabled</label><select id="runtimeGateEnabled"><option value="true">true</option><option value="false">false</option></select></div>
      <div class="row"><label>strictness</label><select id="runtimeGateStrictness">
        <option value="strict">strict</option><option value="normal">normal</option><option value="audit_only">audit_only</option><option value="relaxed">relaxed</option>
      </select></div>
      <div class="checks">
        <label class="check"><input type="checkbox" id="runtimeGateBlockDoNotUse" />block do_not_use</label>
        <label class="check"><input type="checkbox" id="runtimeGateBlockRejected" />block rejected</label>
        <label class="check"><input type="checkbox" id="runtimeGateBlockUnsupported" />block unsupported_fact</label>
        <label class="check"><input type="checkbox" id="runtimeGateBlockConflict" />block conflict</label>
        <label class="check"><input type="checkbox" id="runtimeGateBlockThirdParty" />block third-party judgment</label>
      </div>
      <div class="row"><label>candidate judgment</label><select id="runtimeGateCandidatePolicy"></select></div>
      <div class="row"><label>low sample</label><select id="runtimeGateLowSamplePolicy"></select></div>
      <div class="row"><label>safety boundary</label><select id="runtimeGateSafetyPolicy"></select></div>
      <div class="row"><label>caution skill input</label><select id="runtimeGateCautionSkillPolicy"></select></div>
      <div class="toolbar" style="margin-top:10px">
        <button onclick="loadRuntimeGate()">读取配置</button>
        <button class="primary" onclick="saveRuntimeGate()">保存配置</button>
        <button onclick="resetRuntimeGate()">恢复默认</button>
        <button onclick="loadRuntimeGateDiagnostics()">诊断当前 profile</button>
      </div>
      <pre id="runtimeGateResult">未加载</pre>
    </section>
    <h2 class="section-title">运行态模块</h2>
    <section class="panel">
      <div class="head">
        <div>
          <div class="title">Runtime Modules</div>
          <div class="muted small">控制聊天运行态 guard 和同源证据补全；每个模块可单独关闭或调整严格度，不改蒸馏算法。</div>
        </div>
        <span id="runtimeModulesStatus" class="status unknown">unknown</span>
      </div>
      <div class="grid" id="runtimeModulesGrid"></div>
      <div class="toolbar" style="margin-top:10px">
        <button onclick="loadRuntimeModules()">读取配置</button>
        <button class="primary" onclick="saveRuntimeModules()">保存配置</button>
        <button onclick="resetRuntimeModules()">恢复默认</button>
      </div>
      <pre id="runtimeModulesResult">未加载</pre>
    </section>
    <h2 class="section-title">历史污染隔离</h2>
    <section class="panel">
      <div class="head">
        <div>
          <div class="title">History Isolation</div>
          <div class="muted small">把已生成的劣质 persona_items 隔离到 hidden；只隐藏解释层，不删除 raw_sources。</div>
        </div>
        <span id="historyIsolationStatus" class="status unknown">unknown</span>
      </div>
      <div class="checks">
        <label class="check"><input type="checkbox" id="historyTargetAudit" checked />audit_only</label>
        <label class="check"><input type="checkbox" id="historyTargetRejected" checked />rejected</label>
        <label class="check"><input type="checkbox" id="historyTargetCaution" />caution_only</label>
        <label class="check"><input type="checkbox" id="historyTargetAccept" />accept_runtime</label>
      </div>
      <div class="row"><label>reason filters</label><input id="historyReasonFilters" placeholder="可选；逗号分隔，如 status_candidate,third_party" /></div>
      <div class="row"><label>max_items</label><input id="historyMaxItems" type="number" min="1" max="500" value="100" /></div>
      <div class="toolbar" style="margin-top:10px">
        <button onclick="previewHistoryIsolation()">预览隔离候选</button>
        <button class="primary" onclick="applyHistoryIsolation()">执行隐藏隔离</button>
      </div>
      <pre id="historyIsolationResult">未运行</pre>
    </section>
    <h2 class="section-title">蒸馏 / 知识库插件</h2>
    <div class="two-col">
      <section class="panel">
        <div class="head">
          <div>
            <div class="title">AI 蒸馏 Skill 插件</div>
            <div class="muted small">控制当前 raw_source -> A-M persona_items 的蒸馏倾向和写入规则。</div>
          </div>
          <label class="check"><input type="checkbox" id="distillation-enabled" />enabled</label>
        </div>
        <div class="row"><label>plugin_key</label><input id="distillation-key" /></div>
        <div class="row"><label>strictness</label><select id="distillation-strictness">
          <option value="relaxed">relaxed</option><option value="normal">normal</option><option value="strict">strict</option><option value="audit_only">audit_only</option>
        </select></div>
        <div class="row"><label>tendency JSON</label><textarea id="distillation-tendency"></textarea></div>
        <div class="row"><label>write_rules JSON</label><textarea id="distillation-write-rules"></textarea></div>
        <div class="toolbar" style="margin-top:10px">
          <button onclick="saveDistillationPlugin()">保存蒸馏插件</button>
          <button onclick="resetDistillationPlugin()">恢复默认</button>
        </div>
        <pre id="distillation-plugin-result">未加载</pre>
      </section>
      <section class="panel">
        <div class="head">
          <div>
            <div class="title">A-M 知识库 Skill 插件</div>
            <div class="muted small">控制当前可写入/可分类的 persona library 集合。</div>
          </div>
          <label class="check"><input type="checkbox" id="library-enabled" />enabled</label>
        </div>
        <div class="row"><label>plugin_key</label><input id="library-key" /></div>
        <div class="row"><label>strictness</label><select id="library-strictness">
          <option value="relaxed">relaxed</option><option value="normal">normal</option><option value="strict">strict</option><option value="audit_only">audit_only</option>
        </select></div>
        <div class="row"><label>allowed override JSON</label><textarea id="library-override" placeholder='null 或 ["fact_direct_quotes"]'></textarea></div>
        <div class="row"><label>required keys JSON</label><textarea id="library-required"></textarea></div>
        <div class="toolbar" style="margin-top:10px">
          <button onclick="saveLibraryPlugin()">保存知识库插件</button>
          <button onclick="resetLibraryPlugin()">恢复默认</button>
          <button onclick="loadLibraryCatalog()">查看当前目录</button>
        </div>
        <pre id="library-plugin-result">未加载</pre>
      </section>
    </div>
    <h2 class="section-title">功能策略</h2>
    <div id="policies" class="grid"></div>
    <h2 class="section-title">事件记忆补全调试</h2>
    <section class="panel">
      <div class="row"><label>profile_id</label><input id="completionProfileId" placeholder="必填" /></div>
      <div class="row"><label>source_id</label><input id="completionSourceId" placeholder="可选" /></div>
      <div class="row"><label>dry_run</label><select id="completionDryRun"><option value="true">true</option><option value="false">false</option></select></div>
      <div style="margin-top:10px"><textarea id="completionText" placeholder="输入一段事件记忆，检查缺少时间、地点、人物、事件、感受或证据来源。"></textarea></div>
      <div class="toolbar" style="margin-top:10px"><button onclick="runCompletion()">运行补全检查</button></div>
      <pre id="completionResult">未运行</pre>
    </section>
    <h2 class="section-title">严苛端到端验收</h2>
    <section class="panel">
      <div class="row"><label>profile_id</label><input id="acceptanceProfileId" placeholder="可选；留空会创建隔离 profile" /></div>
      <div class="row"><label>use_model_for_chat</label><select id="acceptanceUseModel"><option value="false">false</option><option value="true">true</option></select></div>
      <div class="toolbar" style="margin-top:10px"><button onclick="runAcceptance()">运行验收</button></div>
      <pre id="acceptanceResult">未运行</pre>
    </section>
    <h2 class="section-title">聊天 / Skill 质量验收</h2>
    <section class="panel">
      <div class="row"><label>profile_id</label><input id="qualityProfileId" placeholder="必填" /></div>
      <div class="row"><label>sample_limit</label><input id="qualitySampleLimit" type="number" min="1" max="200" value="30" /></div>
      <div class="toolbar" style="margin-top:10px">
        <button onclick="runQuality('chat')">验收聊天质量</button>
        <button onclick="runQuality('skill')">验收 Skill 质量</button>
      </div>
      <pre id="qualityResult">未运行</pre>
    </section>
  </main>
  <script>
    const api = "/api/v1";
    async function requestJson(url, options) {
      const res = await fetch(url, options);
      const text = await res.text();
      if (!res.ok) throw new Error(`${res.status} ${text}`);
      return text ? JSON.parse(text) : null;
    }
    function parseJsonField(id, fallback) {
      const value = document.getElementById(id).value.trim();
      if (!value) return fallback;
      return JSON.parse(value);
    }
    function setStatus(id, value) {
      const node = document.getElementById(id);
      if (!node) return;
      node.textContent = value || "unknown";
      node.className = `status ${value || "unknown"}`;
    }
    function globalProfileId() {
      return document.getElementById("globalProfileId").value.trim();
    }
    function syncProfileTargets() {
      const profileId = globalProfileId();
      for (const id of ["completionProfileId","acceptanceProfileId","qualityProfileId"]) {
        const node = document.getElementById(id);
        if (node) node.value = profileId;
      }
    }
    async function loadOverview() {
      const health = await requestJson("/health");
      setStatus("healthStatus", health.status === "ok" ? "ok" : "blocked");
      document.getElementById("healthResult").textContent = JSON.stringify(health, null, 2);
      await Promise.all([loadIntegrity(), loadMonitoring(), loadAdminEvents(), loadRuntimeGate(), loadRuntimeModules()]);
    }
    async function loadIntegrity() {
      const data = await requestJson(`${api}/integrity/report`);
      const blockerCount = data.summary.severity_runtime_blocker || 0;
      const derivedCount = data.summary.severity_derived_orphan || 0;
      const warningCount = data.summary.severity_warning || 0;
      setStatus("integrityStatus", blockerCount ? "blocker" : (derivedCount || warningCount ? "warning" : "ok"));
      document.getElementById("integrityResult").textContent = JSON.stringify({
        summary: data.summary,
        first_issues: data.issues.slice(0, 12)
      }, null, 2);
      return data;
    }
    async function repairIntegrity() {
      const data = await requestJson(`${api}/integrity/repair`, {method:"POST"});
      setStatus("integrityStatus", (data.report_after.summary.severity_runtime_blocker || 0) ? "blocker" : "ok");
      document.getElementById("integrityResult").textContent = JSON.stringify({
        repaired_counts: data.repaired_counts,
        diff: data.diff,
        actions: data.actions,
        after_summary: data.report_after.summary
      }, null, 2);
      return data;
    }
    async function runAcceptanceFromOverview() {
      const profileId = globalProfileId();
      const payload = {profile_id: profileId || null, create_isolated_profile: !profileId, use_model_for_chat: false};
      const data = await requestJson(`${api}/acceptance/e2e/run`, {
        method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)
      });
      setStatus("acceptanceStatus", data.overall_status);
      document.getElementById("acceptanceSummary").textContent = JSON.stringify({
        overall_status: data.overall_status,
        summary: data.summary,
        profile_id: data.profile_id,
        created_profile_id: data.created_profile_id,
        failed_or_blocked: data.checks.filter(item => ["fail","blocked","warning"].includes(item.status)).map(item => ({
          key: item.key,
          status: item.status,
          module: item.module,
          record_ids: item.record_ids,
          reason: item.reason,
          action: item.suggested_action || item.action_hint
        }))
      }, null, 2);
      return data;
    }
    async function loadMonitoring() {
      const profileId = globalProfileId();
      const query = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : "";
      const data = await requestJson(`${api}/monitoring/metrics${query}`);
      setStatus("monitoringStatus", data.overall_level);
      document.getElementById("monitoringResult").textContent = JSON.stringify({
        overall_level: data.overall_level,
        summary: data.summary,
        metrics: data.metrics.map(item => ({
          key: item.metric_key,
          status: item.status,
          level: item.level,
          numerator: item.numerator,
          denominator: item.denominator,
          rate: item.rate,
          sample_quality: item.sample_quality,
          strict_acceptance: item.strict_acceptance,
          attribution: item.attribution,
          missing_data_reason: item.missing_data_reason,
          problems: item.problem_sample_ids
        }))
      }, null, 2);
      return data;
    }
    async function loadAdminEvents() {
      const params = new URLSearchParams();
      const profileId = globalProfileId();
      const eventType = document.getElementById("adminEventType").value;
      const eventStatus = document.getElementById("adminEventStatus").value;
      const workflow = document.getElementById("adminEventWorkflow").value.trim();
      const subjectId = document.getElementById("adminEventSubjectId").value.trim();
      if (profileId) params.set("profile_id", profileId);
      if (eventType) params.set("event_type", eventType);
      if (eventStatus) params.set("status", eventStatus);
      if (workflow) params.set("workflow", workflow);
      if (subjectId) params.set("subject_id", subjectId);
      params.set("limit", "50");
      const data = await requestJson(`${api}/monitoring/events?${params.toString()}`);
      document.getElementById("eventsResult").textContent = JSON.stringify(data.events.map(event => ({
        created_at: event.created_at,
        event_type: event.event_type,
        status: event.status,
        workflow: event.workflow,
        profile_id: event.profile_id,
        subject_id: event.subject_id,
        raw_source_id: event.raw_source_id,
        chat_record_id: event.chat_record_id,
        skill_version_id: event.skill_version_id,
        used_persona_items: event.used_persona_item_ids.length,
        used_raw_sources: event.used_raw_source_ids.length,
        output_summary: event.output_summary,
        error: event.error
      })), null, 2);
      return data;
    }
    const runtimeGateVerdicts = ["accept_runtime","caution_only","audit_only","rejected"];
    function fillRuntimeGatePolicySelects() {
      for (const id of ["runtimeGateCandidatePolicy","runtimeGateLowSamplePolicy","runtimeGateSafetyPolicy","runtimeGateCautionSkillPolicy"]) {
        const node = document.getElementById(id);
        if (node && !node.options.length) {
          node.innerHTML = runtimeGateVerdicts.map(value => `<option value="${value}">${value}</option>`).join("");
        }
      }
    }
    function renderRuntimeGateSettings(settings) {
      fillRuntimeGatePolicySelects();
      document.getElementById("runtimeGateEnabled").value = settings.enabled ? "true" : "false";
      document.getElementById("runtimeGateStrictness").value = settings.strictness;
      document.getElementById("runtimeGateBlockDoNotUse").checked = settings.block_do_not_use;
      document.getElementById("runtimeGateBlockRejected").checked = settings.block_rejected_until_confirmed;
      document.getElementById("runtimeGateBlockUnsupported").checked = settings.block_unsupported_fact;
      document.getElementById("runtimeGateBlockConflict").checked = settings.block_unconfirmed_conflict;
      document.getElementById("runtimeGateBlockThirdParty").checked = settings.block_third_party_target_judgment;
      document.getElementById("runtimeGateCandidatePolicy").value = settings.candidate_judgment_policy;
      document.getElementById("runtimeGateLowSamplePolicy").value = settings.low_sample_policy;
      document.getElementById("runtimeGateSafetyPolicy").value = settings.safety_boundary_policy;
      document.getElementById("runtimeGateCautionSkillPolicy").value = settings.caution_skill_input_policy || "audit_only";
      setStatus("runtimeGateStatus", settings.enabled ? settings.strictness : "disabled");
    }
    function runtimeGatePayloadFromForm() {
      return {
        enabled: document.getElementById("runtimeGateEnabled").value === "true",
        strictness: document.getElementById("runtimeGateStrictness").value,
        block_do_not_use: document.getElementById("runtimeGateBlockDoNotUse").checked,
        block_rejected_until_confirmed: document.getElementById("runtimeGateBlockRejected").checked,
        block_unsupported_fact: document.getElementById("runtimeGateBlockUnsupported").checked,
        block_unconfirmed_conflict: document.getElementById("runtimeGateBlockConflict").checked,
        block_third_party_target_judgment: document.getElementById("runtimeGateBlockThirdParty").checked,
        candidate_judgment_policy: document.getElementById("runtimeGateCandidatePolicy").value,
        low_sample_policy: document.getElementById("runtimeGateLowSamplePolicy").value,
        safety_boundary_policy: document.getElementById("runtimeGateSafetyPolicy").value,
        caution_skill_input_policy: document.getElementById("runtimeGateCautionSkillPolicy").value
      };
    }
    async function loadRuntimeGate() {
      try {
        const settings = await requestJson(`${api}/runtime-gate/settings`);
        renderRuntimeGateSettings(settings);
        document.getElementById("runtimeGateResult").textContent = JSON.stringify(settings, null, 2);
        return settings;
      } catch (error) {
        setStatus("runtimeGateStatus", "blocked");
        document.getElementById("runtimeGateResult").textContent = error.message;
        throw error;
      }
    }
    async function saveRuntimeGate() {
      try {
        const settings = await requestJson(`${api}/runtime-gate/settings`, {
          method:"PATCH",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify(runtimeGatePayloadFromForm())
        });
        renderRuntimeGateSettings(settings);
        document.getElementById("runtimeGateResult").textContent = JSON.stringify(settings, null, 2);
        return settings;
      } catch (error) {
        alert(`Runtime Gate 配置失败：${error.message}`);
        throw error;
      }
    }
    async function resetRuntimeGate() {
      try {
        const settings = await requestJson(`${api}/runtime-gate/settings/reset`, {method:"POST"});
        renderRuntimeGateSettings(settings);
        document.getElementById("runtimeGateResult").textContent = JSON.stringify(settings, null, 2);
        return settings;
      } catch (error) {
        alert(`Runtime Gate 重置失败：${error.message}`);
        throw error;
      }
    }
    async function loadRuntimeGateDiagnostics() {
      const profileId = globalProfileId();
      if (!profileId) {
        alert("请先填写顶部 profile_id");
        return null;
      }
      const data = await requestJson(`${api}/runtime-gate/profiles/${encodeURIComponent(profileId)}/diagnostics`);
      const summary = data.summary || {};
      setStatus("runtimeGateStatus", (summary.blocked_count || 0) ? "warning" : "ok");
      document.getElementById("runtimeGateResult").textContent = JSON.stringify({
        summary,
        blocked_samples: summary.blocked_samples || [],
        first_decisions: (data.decisions || []).slice(0, 30)
      }, null, 2);
      return data;
    }
    const runtimeModuleKeys = [
      ["boundary_guard", "边界语义 guard"],
      ["expression_guard", "通用安抚拦截"],
      ["closure_guard", "尾巴收束 guard"],
      ["attribution_guard", "归因边界 guard"],
      ["evidence_extension", "同源证据补全"]
    ];
    const runtimeModuleStrictness = ["relaxed","normal","strict","audit_only"];
    function renderRuntimeModules(settings) {
      const grid = document.getElementById("runtimeModulesGrid");
      grid.innerHTML = runtimeModuleKeys.map(([key, label]) => {
        const module = settings[key] || {};
        const extra = key === "evidence_extension" ? `
          <div class="row"><label>max_extensions</label><input id="${key}-max_extensions" type="number" min="0" max="20" value="${module.max_extensions ?? 2}" /></div>
          <div class="row"><label>max_chars</label><input id="${key}-max_chars" type="number" min="20" max="2000" value="${module.max_chars ?? 260}" /></div>
        ` : "";
        const toggles = Object.entries(module)
          .filter(([field, value]) => typeof value === "boolean" && field !== "enabled")
          .map(([field, value]) => `<label class="check"><input type="checkbox" id="${key}-${field}" ${value ? "checked" : ""} />${field}</label>`)
          .join("");
        return `
          <section class="panel">
            <div class="head">
              <div>
                <div class="title">${label}</div>
                <div class="muted small">${key}</div>
              </div>
              <label class="check"><input type="checkbox" id="${key}-enabled" ${module.enabled ? "checked" : ""} />enabled</label>
            </div>
            <div class="row"><label>strictness</label><select id="${key}-strictness">
              ${runtimeModuleStrictness.map(item => `<option value="${item}" ${module.strictness === item ? "selected" : ""}>${item}</option>`).join("")}
            </select></div>
            <div class="checks">${toggles}</div>
            ${extra}
          </section>
        `;
      }).join("");
      const disabled = runtimeModuleKeys.filter(([key]) => settings[key] && settings[key].enabled === false).length;
      setStatus("runtimeModulesStatus", disabled ? "warning" : "strict");
    }
    function runtimeModulesPayloadFromForm() {
      const payload = {};
      for (const [key] of runtimeModuleKeys) {
        const module = {
          enabled: document.getElementById(`${key}-enabled`).checked,
          strictness: document.getElementById(`${key}-strictness`).value
        };
        for (const node of document.querySelectorAll(`[id^="${key}-"]`)) {
          const field = node.id.slice(key.length + 1);
          if (field === "enabled" || field === "strictness") continue;
          if (node.type === "checkbox") module[field] = node.checked;
          if (node.type === "number") module[field] = Number(node.value || 0);
        }
        payload[key] = module;
      }
      return payload;
    }
    async function loadRuntimeModules() {
      try {
        const settings = await requestJson(`${api}/runtime-modules/settings`);
        renderRuntimeModules(settings);
        document.getElementById("runtimeModulesResult").textContent = JSON.stringify(settings, null, 2);
        return settings;
      } catch (error) {
        setStatus("runtimeModulesStatus", "blocked");
        document.getElementById("runtimeModulesResult").textContent = error.message;
        throw error;
      }
    }
    async function saveRuntimeModules() {
      try {
        const settings = await requestJson(`${api}/runtime-modules/settings`, {
          method:"PATCH",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify(runtimeModulesPayloadFromForm())
        });
        renderRuntimeModules(settings);
        document.getElementById("runtimeModulesResult").textContent = JSON.stringify(settings, null, 2);
        return settings;
      } catch (error) {
        alert(`Runtime Modules 配置失败：${error.message}`);
        throw error;
      }
    }
    async function resetRuntimeModules() {
      try {
        const settings = await requestJson(`${api}/runtime-modules/settings/reset`, {method:"POST"});
        renderRuntimeModules(settings);
        document.getElementById("runtimeModulesResult").textContent = JSON.stringify(settings, null, 2);
        return settings;
      } catch (error) {
        alert(`Runtime Modules 重置失败：${error.message}`);
        throw error;
      }
    }
    function historyIsolationPayload(dryRun) {
      const target_verdicts = [];
      if (document.getElementById("historyTargetAccept").checked) target_verdicts.push("accept_runtime");
      if (document.getElementById("historyTargetCaution").checked) target_verdicts.push("caution_only");
      if (document.getElementById("historyTargetAudit").checked) target_verdicts.push("audit_only");
      if (document.getElementById("historyTargetRejected").checked) target_verdicts.push("rejected");
      const target_reasons = document.getElementById("historyReasonFilters").value
        .split(",")
        .map(item => item.trim())
        .filter(Boolean);
      return {
        dry_run: dryRun,
        target_verdicts,
        target_reasons,
        max_items: Number(document.getElementById("historyMaxItems").value || 100),
        updated_by: "backend-admin"
      };
    }
    async function previewHistoryIsolation() {
      const profileId = globalProfileId();
      if (!profileId) {
        alert("请先填写顶部 profile_id");
        return null;
      }
      const data = await requestJson(`${api}/history-isolation/profiles/${encodeURIComponent(profileId)}/preview`, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(historyIsolationPayload(true))
      });
      setStatus("historyIsolationStatus", data.summary.candidate_count ? "warning" : "ok");
      document.getElementById("historyIsolationResult").textContent = JSON.stringify({
        summary: data.summary,
        candidates: data.candidates.slice(0, 30)
      }, null, 2);
      return data;
    }
    async function applyHistoryIsolation() {
      const profileId = globalProfileId();
      if (!profileId) {
        alert("请先填写顶部 profile_id");
        return null;
      }
      const data = await requestJson(`${api}/history-isolation/profiles/${encodeURIComponent(profileId)}/apply`, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(historyIsolationPayload(false))
      });
      setStatus("historyIsolationStatus", data.summary.hidden_count ? "audit" : "ok");
      document.getElementById("historyIsolationResult").textContent = JSON.stringify({
        summary: data.summary,
        candidates: data.candidates.slice(0, 30)
      }, null, 2);
      await loadRuntimeGateDiagnostics().catch(() => {});
      return data;
    }
    async function loadPlugins() {
      const [distillation, library] = await Promise.all([
        requestJson(`${api}/distillation-plugins`),
        requestJson(`${api}/library-plugins`)
      ]);
      const currentDistillation = distillation.current;
      document.getElementById("distillation-enabled").checked = currentDistillation.enabled;
      document.getElementById("distillation-key").value = currentDistillation.selected_plugin_key;
      document.getElementById("distillation-strictness").value = currentDistillation.strictness;
      document.getElementById("distillation-tendency").value = JSON.stringify(currentDistillation.tendency, null, 2);
      document.getElementById("distillation-write-rules").value = JSON.stringify(currentDistillation.write_rules, null, 2);
      document.getElementById("distillation-plugin-result").textContent = JSON.stringify(distillation, null, 2);

      const currentLibrary = library.current;
      document.getElementById("library-enabled").checked = currentLibrary.enabled;
      document.getElementById("library-key").value = currentLibrary.selected_plugin_key;
      document.getElementById("library-strictness").value = currentLibrary.strictness;
      document.getElementById("library-override").value = JSON.stringify(currentLibrary.allowed_library_keys_override, null, 2);
      document.getElementById("library-required").value = JSON.stringify(currentLibrary.min_required_library_keys, null, 2);
      document.getElementById("library-plugin-result").textContent = JSON.stringify(library, null, 2);
    }
    async function saveDistillationPlugin() {
      try {
        const payload = {
          selected_plugin_key: document.getElementById("distillation-key").value.trim(),
          enabled: document.getElementById("distillation-enabled").checked,
          strictness: document.getElementById("distillation-strictness").value,
          tendency: parseJsonField("distillation-tendency", {}),
          write_rules: parseJsonField("distillation-write-rules", {}),
          updated_by: "backend-admin"
        };
        const data = await requestJson(`${api}/distillation-plugins/current`, {
          method:"PATCH", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)
        });
        document.getElementById("distillation-plugin-result").textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        alert(`蒸馏插件配置失败：${error.message}`);
      }
    }
    async function resetDistillationPlugin() {
      const data = await requestJson(`${api}/distillation-plugins/current/reset`, {method:"POST"});
      document.getElementById("distillation-plugin-result").textContent = JSON.stringify(data, null, 2);
      await loadPlugins();
    }
    async function saveLibraryPlugin() {
      try {
        const payload = {
          selected_plugin_key: document.getElementById("library-key").value.trim(),
          enabled: document.getElementById("library-enabled").checked,
          strictness: document.getElementById("library-strictness").value,
          allowed_library_keys_override: parseJsonField("library-override", null),
          min_required_library_keys: parseJsonField("library-required", []),
          updated_by: "backend-admin"
        };
        const data = await requestJson(`${api}/library-plugins/current`, {
          method:"PATCH", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)
        });
        document.getElementById("library-plugin-result").textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        alert(`知识库插件配置失败：${error.message}`);
      }
    }
    async function resetLibraryPlugin() {
      const data = await requestJson(`${api}/library-plugins/current/reset`, {method:"POST"});
      document.getElementById("library-plugin-result").textContent = JSON.stringify(data, null, 2);
      await loadPlugins();
    }
    async function loadLibraryCatalog() {
      const data = await requestJson(`${api}/library-plugins/current/catalog`);
      document.getElementById("library-plugin-result").textContent = JSON.stringify(data, null, 2);
    }
    const layers = ["raw_source","persona_item","uncertain_item","question_target","chat_record","skill_version","monitoring_event"];
    function renderPolicy(policy) {
      const checks = layers.map(layer => `
        <label class="check"><input type="checkbox" id="${policy.feature_key}-${layer}" ${policy.write_rules[layer] ? "checked" : ""} />${layer}</label>
      `).join("");
      return `
        <section class="panel">
          <div class="head">
            <div><div class="title">${policy.name}</div><div class="muted small"><code>${policy.feature_key}</code></div></div>
            <label class="check"><input type="checkbox" id="${policy.feature_key}-enabled" ${policy.enabled ? "checked" : ""} />enabled</label>
          </div>
          <p class="muted">${policy.description}</p>
          <div class="row"><label>algorithm_key</label><input id="${policy.feature_key}-algorithm" value="${policy.algorithm_key}" /></div>
          <div class="row"><label>strictness</label><select id="${policy.feature_key}-strictness">
            ${["relaxed","normal","strict","audit_only"].map(item => `<option value="${item}" ${policy.strictness === item ? "selected" : ""}>${item}</option>`).join("")}
          </select></div>
          <div class="row"><label>thresholds JSON</label><input id="${policy.feature_key}-thresholds" value='${JSON.stringify(policy.thresholds).replaceAll("'", "&#39;")}' /></div>
          <div class="checks">${checks}</div>
          <div class="toolbar" style="margin-top:10px">
            <button onclick="savePolicy('${policy.feature_key}')">保存策略</button>
            <button onclick="resetPolicy('${policy.feature_key}')">恢复默认</button>
          </div>
        </section>`;
    }
    async function loadPolicies() {
      const policies = await requestJson(`${api}/feature-policies`);
      document.getElementById("policies").innerHTML = policies.map(renderPolicy).join("");
    }
    async function savePolicy(featureKey) {
      let thresholds = {};
      try { thresholds = JSON.parse(document.getElementById(`${featureKey}-thresholds`).value || "{}"); }
      catch { alert("thresholds JSON 格式错误"); return; }
      const write_rules = {};
      for (const layer of layers) write_rules[layer] = document.getElementById(`${featureKey}-${layer}`).checked;
      await requestJson(`${api}/feature-policies/${featureKey}`, {
        method:"PATCH",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          enabled: document.getElementById(`${featureKey}-enabled`).checked,
          algorithm_key: document.getElementById(`${featureKey}-algorithm`).value.trim(),
          strictness: document.getElementById(`${featureKey}-strictness`).value,
          thresholds,
          write_rules,
          updated_by:"backend-admin"
        })
      });
      await loadPolicies();
    }
    async function resetPolicy(featureKey) {
      await requestJson(`${api}/feature-policies/${featureKey}/reset`, {method:"POST"});
      await loadPolicies();
    }
    async function runCompletion() {
      const sourceId = document.getElementById("completionSourceId").value.trim();
      const payload = {
        profile_id: document.getElementById("completionProfileId").value.trim(),
        source_id: sourceId || null,
        dry_run: document.getElementById("completionDryRun").value === "true",
        text: document.getElementById("completionText").value.trim()
      };
      document.getElementById("completionResult").textContent = JSON.stringify(await requestJson(`${api}/memory-completion/event`, {
        method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)
      }), null, 2);
    }
    async function runAcceptance() {
      const profileId = document.getElementById("acceptanceProfileId").value.trim();
      const payload = {
        profile_id: profileId || null,
        create_isolated_profile: !profileId,
        use_model_for_chat: document.getElementById("acceptanceUseModel").value === "true"
      };
      document.getElementById("acceptanceResult").textContent = JSON.stringify(await requestJson(`${api}/acceptance/e2e/run`, {
        method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)
      }), null, 2);
    }
    async function runQuality(kind) {
      const payload = {
        profile_id: document.getElementById("qualityProfileId").value.trim(),
        sample_limit: Number(document.getElementById("qualitySampleLimit").value || 30),
        include_audit_units: true
      };
      document.getElementById("qualityResult").textContent = JSON.stringify(await requestJson(`${api}/quality-validation/${kind}`, {
        method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)
      }), null, 2);
    }
    loadPlugins().catch(error => {
      document.getElementById("distillation-plugin-result").textContent = error.message;
      document.getElementById("library-plugin-result").textContent = error.message;
    });
    fillRuntimeGatePolicySelects();
    loadRuntimeGate().catch(() => {});
    loadRuntimeModules().catch(() => {});
    loadPolicies().catch(error => {
      document.getElementById("policies").innerHTML = `<section class="panel danger">${error.message}</section>`;
    });
    loadOverview().catch(error => {
      setStatus("healthStatus", "blocked");
      document.getElementById("healthResult").textContent = error.message;
    });
  </script>
</body>
</html>
"""
