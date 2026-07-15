from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from app.schemas.monitoring import MonitoringEvent, MonitoringEventListResponse, MonitoringEventStatus, MonitoringEventType
from app.schemas.monitoring import MonitoringMetricConfig, MonitoringMetricConfigUpdate
from app.schemas.monitoring import MonitoringMetricResult, MonitoringReport
from app.services.monitoring_metrics import build_monitoring_report, calculate_metric
from app.services.monitoring_store import (
    get_metric_config,
    get_monitoring_event,
    list_metric_configs,
    list_monitoring_events,
    reset_metric_config,
    update_metric_config,
)
from app.services.profile_store import get_profile

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/metrics", response_model=MonitoringReport)
def read_monitoring_metrics(profile_id: UUID | None = Query(default=None)) -> MonitoringReport:
    if profile_id is not None:
        get_profile(profile_id)
    return build_monitoring_report(profile_id=profile_id)


@router.get("/metrics/{metric_key}", response_model=MonitoringMetricResult)
def read_monitoring_metric(metric_key: str, profile_id: UUID | None = Query(default=None)) -> MonitoringMetricResult:
    if profile_id is not None:
        get_profile(profile_id)
    try:
        return calculate_metric(metric_key, profile_id=profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoring metric not found") from exc


@router.get("/configs", response_model=list[MonitoringMetricConfig])
def read_monitoring_configs() -> list[MonitoringMetricConfig]:
    return list_metric_configs()


@router.get("/configs/{metric_key}", response_model=MonitoringMetricConfig)
def read_monitoring_config(metric_key: str) -> MonitoringMetricConfig:
    return get_metric_config(metric_key)


@router.patch("/configs/{metric_key}", response_model=MonitoringMetricConfig)
def patch_monitoring_config(metric_key: str, payload: MonitoringMetricConfigUpdate) -> MonitoringMetricConfig:
    return update_metric_config(metric_key, payload)


@router.post("/configs/{metric_key}/reset", response_model=MonitoringMetricConfig)
def reset_monitoring_config(metric_key: str) -> MonitoringMetricConfig:
    return reset_metric_config(metric_key)


@router.get("/events", response_model=MonitoringEventListResponse)
def read_monitoring_events(
    event_type: MonitoringEventType | None = Query(default=None),
    status: MonitoringEventStatus | None = Query(default=None),
    profile_id: UUID | None = Query(default=None),
    raw_source_id: UUID | None = Query(default=None),
    chat_record_id: UUID | None = Query(default=None),
    skill_version_id: UUID | None = Query(default=None),
    subject_id: str | None = Query(default=None, min_length=1, max_length=160),
    workflow: str | None = Query(default=None, min_length=1, max_length=160),
    limit: int = Query(default=100, ge=1, le=500),
) -> MonitoringEventListResponse:
    if profile_id is not None:
        get_profile(profile_id)
    return MonitoringEventListResponse(
        events=list_monitoring_events(
            event_type=event_type,
            status=status,
            profile_id=profile_id,
            raw_source_id=raw_source_id,
            chat_record_id=chat_record_id,
            skill_version_id=skill_version_id,
            subject_id=subject_id,
            workflow=workflow,
            limit=limit,
        )
    )


@router.get("/events/{event_id}", response_model=MonitoringEvent)
def read_monitoring_event(event_id: UUID) -> MonitoringEvent:
    return get_monitoring_event(event_id)


@router.get("/dashboard", response_class=HTMLResponse)
def monitoring_dashboard() -> HTMLResponse:
    return HTMLResponse(_DASHBOARD_HTML)


_DASHBOARD_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>后端数据监控</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --border: #d7dce3;
      --ok: #0f766e;
      --warn: #b45309;
      --block: #b91c1c;
      --audit: #4b5563;
      --blue: #2563eb;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
    }
    header {
      padding: 18px 24px;
      border-bottom: 1px solid var(--border);
      background: var(--panel);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 { font-size: 20px; margin: 0; }
    main { padding: 20px 24px 40px; max-width: 1440px; margin: 0 auto; }
    .toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    input, select, button {
      height: 34px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      padding: 0 10px;
      font: inherit;
    }
    button { cursor: pointer; }
    button.primary { background: var(--blue); border-color: var(--blue); color: #fff; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
    }
    .metric-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
    .metric-title { font-weight: 700; line-height: 1.3; }
    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 64px;
      height: 24px;
      border-radius: 999px;
      padding: 0 8px;
      font-size: 12px;
      border: 1px solid var(--border);
      color: var(--audit);
      white-space: nowrap;
    }
    .ok { color: var(--ok); border-color: #99d3cb; background: #eefbf8; }
    .warning { color: var(--warn); border-color: #f1c37d; background: #fff7ed; }
    .blocker { color: var(--block); border-color: #f0aaa8; background: #fff1f2; }
    .audit, .disabled, .unknown { color: var(--audit); background: #f3f4f6; }
    .number { font-size: 30px; font-weight: 750; margin: 10px 0 2px; }
    .muted { color: var(--muted); }
    .small { font-size: 12px; }
    .row { display: grid; grid-template-columns: 120px 1fr; gap: 8px; align-items: center; margin-top: 8px; }
    .row input, .row select { width: 100%; }
    details { margin-top: 10px; }
    summary { cursor: pointer; color: var(--blue); }
    code, pre {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
    }
    pre {
      white-space: pre-wrap;
      max-height: 180px;
      overflow: auto;
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }
    th, td {
      text-align: left;
      padding: 9px 10px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }
    th { background: #f8fafc; font-weight: 700; }
    td { font-size: 13px; }
    .section-title { margin: 22px 0 10px; font-size: 16px; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>后端数据监控</h1>
      <div class="muted small">指标算法、严格程度和开关均由后端配置控制。</div>
    </div>
    <div class="toolbar">
      <input id="profileId" placeholder="profile_id 可选" size="36" />
      <button class="primary" onclick="loadAll()">刷新</button>
      <a href="/docs" target="_blank">OpenAPI</a>
    </div>
  </header>
  <main>
    <div id="summary" class="panel">加载中...</div>
    <h2 class="section-title">指标</h2>
    <div id="metrics" class="grid"></div>
    <h2 class="section-title">AI 蒸馏日志 / AI 使用 Skill 回复日志</h2>
    <div class="toolbar" style="margin-bottom:10px">
      <select id="eventType">
        <option value="">全部日志</option>
        <option value="acceptance">严苛验收日志</option>
        <option value="distillation">AI 蒸馏日志</option>
        <option value="confirmation">确认/纠错日志</option>
        <option value="skill_generation">Skill 生成日志</option>
        <option value="chat_skill_usage">AI 使用 Skill 回复日志</option>
      </select>
      <button onclick="loadEvents()">刷新日志</button>
    </div>
    <div id="events"></div>
  </main>
  <script>
    const api = "/api/v1/monitoring";
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[char]));
    const escapeAttr = escapeHtml;
    const levelClass = (level) => ["ok","warning","blocker","audit","disabled","unknown"].includes(level) ? level : "unknown";
    const pct = (rate) => rate === null || rate === undefined ? "不可计算" : `${(rate * 100).toFixed(2)}%`;
    const profileQuery = () => {
      const value = document.getElementById("profileId").value.trim();
      return value ? `?profile_id=${encodeURIComponent(value)}` : "";
    };
    async function requestJson(url, options) {
      const res = await fetch(url, options);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`${res.status} ${text}`);
      }
      return await res.json();
    }
    async function loadAll() {
      await loadMetrics();
      await loadEvents();
    }
    async function loadMetrics() {
      const report = await requestJson(`${api}/metrics${profileQuery()}`);
      document.getElementById("summary").innerHTML = `
        <div class="metric-head">
          <div>
            <div class="metric-title">总体状态</div>
            <div class="muted small">生成时间：${escapeHtml(report.generated_at)}</div>
          </div>
          <span class="badge ${levelClass(report.overall_level)}">${escapeHtml(report.overall_level)}</span>
        </div>
        <pre>${escapeHtml(JSON.stringify(report.summary, null, 2))}</pre>
      `;
      document.getElementById("metrics").innerHTML = report.metrics.map(renderMetric).join("");
    }
    function renderMetric(metric) {
      const thresholdText = JSON.stringify(metric.thresholds);
      return `
        <section class="panel">
          <div class="metric-head">
            <div>
              <div class="metric-title">${escapeHtml(metric.name)}</div>
              <div class="muted small"><code>${escapeHtml(metric.metric_key)}</code></div>
            </div>
            <span class="badge ${levelClass(metric.level)}">${escapeHtml(metric.level)}</span>
          </div>
          <div class="number">${escapeHtml(pct(metric.rate))}</div>
          <div class="muted">分子 / 分母：${escapeHtml(metric.numerator)} / ${escapeHtml(metric.denominator)}</div>
          <div class="muted small">状态：${escapeHtml(metric.status)}；算法：${escapeHtml(metric.algorithm_key)}</div>
          <p>${escapeHtml(metric.calculation_note)}</p>
          ${metric.missing_data_reason ? `<p class="warning">缺数据原因：${escapeHtml(metric.missing_data_reason)}</p>` : ""}
          <div class="muted small">归因：${escapeHtml(metric.attribution)}</div>
          ${metric.attribution_note ? `<p>${escapeHtml(metric.attribution_note)}</p>` : ""}
          ${metric.action_hint ? `<p class="muted">处理建议：${escapeHtml(metric.action_hint)}</p>` : ""}
          <div class="row"><label>开关</label><select id="${metric.metric_key}-enabled"><option value="true">enabled</option><option value="false">disabled</option></select></div>
          <div class="row"><label>严格程度</label><select id="${metric.metric_key}-strictness">
            <option value="relaxed">relaxed</option><option value="normal">normal</option><option value="strict">strict</option><option value="audit_only">audit_only</option>
          </select></div>
          <div class="row"><label>算法 key</label><input id="${escapeAttr(metric.metric_key)}-algorithm" value="${escapeAttr(metric.algorithm_key)}" /></div>
          <div class="row"><label>阈值 JSON</label><input id="${escapeAttr(metric.metric_key)}-thresholds" value='${escapeAttr(thresholdText)}' /></div>
          <div class="row"><label>窗口天数</label><input id="${escapeAttr(metric.metric_key)}-window" type="number" min="1" max="3650" value="${escapeAttr(metric.window_days)}" /></div>
          <div class="row"><label>样本数量</label><input id="${escapeAttr(metric.metric_key)}-sample" type="number" min="1" max="500" value="${escapeAttr(metric.sample_limit)}" /></div>
          <div class="toolbar" style="margin-top:10px">
            <button onclick="saveConfig('${escapeAttr(metric.metric_key)}')">保存配置</button>
            <button onclick="resetConfig('${escapeAttr(metric.metric_key)}')">恢复默认</button>
          </div>
          <details>
            <summary>样本明细</summary>
            <pre>sample_ids:
${escapeHtml(metric.sample_ids.join("\\n") || "none")}

problem_sample_ids:
${escapeHtml(metric.problem_sample_ids.join("\\n") || "none")}</pre>
          </details>
        </section>
      `;
    }
    async function syncConfigControls() {
      const configs = await requestJson(`${api}/configs`);
      for (const config of configs) {
        const enabled = document.getElementById(`${config.metric_key}-enabled`);
        const strictness = document.getElementById(`${config.metric_key}-strictness`);
        if (enabled) enabled.value = String(config.enabled);
        if (strictness) strictness.value = config.strictness;
      }
    }
    async function saveConfig(metricKey) {
      let thresholds = {};
      try {
        thresholds = JSON.parse(document.getElementById(`${metricKey}-thresholds`).value || "{}");
      } catch (error) {
        alert("阈值 JSON 格式错误");
        return;
      }
      await requestJson(`${api}/configs/${metricKey}`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          enabled: document.getElementById(`${metricKey}-enabled`).value === "true",
          strictness: document.getElementById(`${metricKey}-strictness`).value,
          algorithm_key: document.getElementById(`${metricKey}-algorithm`).value.trim(),
          thresholds,
          window_days: Number(document.getElementById(`${metricKey}-window`).value),
          sample_limit: Number(document.getElementById(`${metricKey}-sample`).value),
          updated_by: "backend-dashboard"
        })
      });
      await loadMetrics();
      await syncConfigControls();
    }
    async function resetConfig(metricKey) {
      await requestJson(`${api}/configs/${metricKey}/reset`, {method: "POST"});
      await loadMetrics();
      await syncConfigControls();
    }
    async function loadEvents() {
      const type = document.getElementById("eventType").value;
      const params = new URLSearchParams();
      const profile = document.getElementById("profileId").value.trim();
      if (type) params.set("event_type", type);
      if (profile) params.set("profile_id", profile);
      params.set("limit", "100");
      const data = await requestJson(`${api}/events?${params.toString()}`);
      if (!data.events.length) {
        document.getElementById("events").innerHTML = `<div class="panel muted">暂无日志。</div>`;
        return;
      }
      document.getElementById("events").innerHTML = `
        <table>
          <thead><tr><th>时间</th><th>类型</th><th>状态</th><th>对象</th><th>摘要</th><th>使用证据</th></tr></thead>
          <tbody>
            ${data.events.map(event => `
              <tr>
                <td>${escapeHtml(event.created_at)}</td>
                <td>${escapeHtml(event.event_type)}<br><span class="muted small">${escapeHtml(event.workflow)}</span></td>
                <td>${escapeHtml(event.status)}</td>
                <td><code>${escapeHtml(event.subject_id || event.id)}</code></td>
                <td>${escapeHtml(event.output_summary || event.error || "")}</td>
                <td class="small">persona=${escapeHtml(event.used_persona_item_ids.length)}<br>raw=${escapeHtml(event.used_raw_source_ids.length)}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      `;
    }
    loadAll().then(syncConfigControls).catch(error => {
      document.getElementById("summary").innerHTML = `<span class="blocker">加载失败：${escapeHtml(error.message)}</span>`;
    });
  </script>
</body>
</html>
"""
