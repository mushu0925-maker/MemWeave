from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from app.core.config import get_settings
from app.schemas.system_self_check import SystemCheckStatus, SystemSelfCheckItem, SystemSelfCheckResponse
from app.services.acceptance_runner import ACCEPTANCE_ALGORITHMS
from app.services.ai_config_store import read_ai_config
from app.services.feature_policy_store import get_feature_policy
from app.services.local_database import get_storage_status
from app.services.persona_item_store import list_persona_items
from app.services.raw_source_store import list_raw_sources
from app.services.source_segment_store import list_extracted_segments, list_source_segments
from app.services.voice_generation_service import voice_generation_status


def _now() -> datetime:
    return datetime.now(UTC)


def _check(
    key: str,
    label: str,
    status: SystemCheckStatus,
    *,
    summary: str,
    detail: str = "",
    action: str = "",
    metadata: dict[str, object] | None = None,
) -> SystemSelfCheckItem:
    return SystemSelfCheckItem(
        key=key,
        label=label,
        status=status,
        summary=summary,
        detail=detail,
        action=action,
        metadata=metadata or {},
    )


def _overall(checks: list[SystemSelfCheckItem]) -> SystemCheckStatus:
    for status in ("blocked", "fail", "warning"):
        if any(check.status == status for check in checks):
            return status  # type: ignore[return-value]
    return "pass"


def _required_routes(api_prefix: str) -> list[str]:
    return [
        "/health",
        f"{api_prefix}/backups/export",
        f"{api_prefix}/config/ai",
        f"{api_prefix}/raw-sources",
        f"{api_prefix}/storage/status",
        f"{api_prefix}/source-segments",
        f"{api_prefix}/voice/status",
        f"{api_prefix}/acceptance/e2e/run",
        f"{api_prefix}/system/self-check",
    ]


def build_system_self_check(*, available_paths: set[str]) -> SystemSelfCheckResponse:
    settings = get_settings()
    required_routes = {path: path in available_paths for path in _required_routes(settings.api_v1_prefix)}
    missing_routes = [path for path, present in required_routes.items() if not present]
    checks: list[SystemSelfCheckItem] = [
        _check(
            "api_routes_current",
            "后端接口版本",
            "pass" if not missing_routes else "blocked",
            summary="当前后端包含桌面端需要的核心 API。" if not missing_routes else "当前后端缺少核心 API，可能是旧服务还在占用端口。",
            detail=", ".join(missing_routes),
            action="重启后端或运行一键启动脚本，确认 8000 端口加载的是当前代码。" if missing_routes else "",
            metadata={"required_routes": required_routes},
        )
    ]

    try:
        storage_status = get_storage_status()
        checks.append(
            _check(
                "storage_status",
                "本地存储",
                "pass",
                summary=f"当前使用 {storage_status['active_backend']} 存储，数据目录可访问。",
                detail=f"JSON 文件 {storage_status['json_file_count']} 个，SQLite 文档 {storage_status['sqlite_document_count']} 个。",
                metadata={
                    "active_backend": storage_status["active_backend"],
                    "data_dir": storage_status["data_dir"],
                    "sqlite_path": storage_status["sqlite_path"],
                    "json_file_count": storage_status["json_file_count"],
                    "sqlite_document_count": storage_status["sqlite_document_count"],
                },
            )
        )
    except Exception as exc:  # pragma: no cover - defensive visibility path.
        checks.append(
            _check(
                "storage_status",
                "本地存储",
                "blocked",
                summary="本地存储状态读取失败。",
                detail=str(exc)[:1000],
                action="先修复 backend/data 下的损坏文件或权限问题，再继续验收。",
            )
        )

    try:
        raw_sources = list_raw_sources(include_deleted=True)
        persona_items = list_persona_items(include_hidden=True)
        source_segments = list_source_segments()
        extracted_segments = list_extracted_segments()
        segmented_raw_source_ids = {segment.raw_source_id for segment in source_segments}
        raw_sources_without_segments = [
            raw_source
            for raw_source in raw_sources
            if raw_source.deleted_at is None and raw_source.id not in segmented_raw_source_ids
        ]
        pending_segments = [
            segment
            for segment in source_segments
            if segment.attribution_status in {"pending", "needs_review"}
        ]
        if raw_sources and not source_segments:
            segment_status: SystemCheckStatus = "fail"
            segment_summary = "已有原始资料，但没有片段归属记录。"
            segment_action = "打开 Library 的片段确认页执行“补齐全部旧资料”，或调用 POST /api/v1/source-segments/backfill。"
        elif raw_sources_without_segments:
            segment_status = "warning"
            segment_summary = (
                f"片段层可用，但还有 {len(raw_sources_without_segments)} 条历史资料未补片段，"
                f"{len(pending_segments)} 条片段待确认。"
            )
            segment_action = "到 Library 的片段确认页执行“补齐全部旧资料”，并处理待确认归属；声音参考必须确认后才能生成。"
        elif pending_segments:
            segment_status = "warning"
            segment_summary = f"片段层可用，但还有 {len(pending_segments)} 条需要确认归属或用途。"
            segment_action = "到 Library 片段确认里处理待确认资料，声音参考必须确认后才能生成。"
        else:
            segment_status = "pass"
            segment_summary = "片段层可用，当前没有待确认片段。"
            segment_action = ""
        checks.append(
            _check(
                "source_segment_layer",
                "资料片段归属",
                segment_status,
                summary=segment_summary,
                detail=f"raw_sources={len(raw_sources)}, persona_items={len(persona_items)}, source_segments={len(source_segments)}, extracted_segments={len(extracted_segments)}",
                action=segment_action,
                metadata={
                    "raw_source_count": len(raw_sources),
                    "persona_item_count": len(persona_items),
                    "source_segment_count": len(source_segments),
                    "extracted_segment_count": len(extracted_segments),
                    "raw_sources_without_segment_count": len(raw_sources_without_segments),
                    "pending_segment_count": len(pending_segments),
                },
            )
        )
    except Exception as exc:  # pragma: no cover - defensive visibility path.
        checks.append(
            _check(
                "source_segment_layer",
                "资料片段归属",
                "blocked",
                summary="片段层读取失败。",
                detail=str(exc)[:1000],
                action="先检查 /api/v1/source-segments 和 source_segments.json。",
            )
        )

    ai_config = read_ai_config()
    checks.append(
        _check(
            "ai_runtime_config",
            "模型配置",
            "pass" if (ai_config.chat_enabled or ai_config.persona_enabled) else "warning",
            summary="大模型已配置，可用于资料提取和聊天。" if ai_config.llm_enabled else "大模型未配置，正式资料提取和高质量聊天会被阻断或降级。",
            detail=(
                f"chat={ai_config.chat_effective_base_url or 'default'} / {ai_config.chat_effective_model}; "
                f"classification={ai_config.persona_effective_base_url or 'default'} / {ai_config.persona_effective_model}; "
                f"vision={ai_config.vision_effective_base_url or 'default'} / {ai_config.vision_effective_model}; "
                f"asr={ai_config.asr_effective_base_url or 'default'} / {ai_config.asr_effective_model}"
            ),
            action="在设置里填写 API Key、接口地址和模型后，再运行连接测试。" if not ai_config.llm_enabled else "",
            metadata={
                "llm_enabled": ai_config.llm_enabled,
                "chat_enabled": ai_config.chat_enabled,
                "persona_enabled": ai_config.persona_enabled,
                "vision_enabled": ai_config.vision_enabled,
                "asr_enabled": ai_config.asr_enabled,
                "llm_model": ai_config.llm_model,
                "chat_model": ai_config.chat_effective_model,
                "persona_model": ai_config.persona_effective_model,
                "vision_model": ai_config.vision_effective_model,
                "asr_model": ai_config.asr_effective_model,
            },
        )
    )

    if not ai_config.enable_vision_ocr:
        vision_status: SystemCheckStatus = "warning"
        vision_summary = "视觉/OCR 当前关闭；图片会保存为原始资料，但不会识别图中文字或场景。"
        vision_action = "需要图片识别时，在设置的高级选项里开启视觉识别，并确认接口支持所选视觉模型。"
    elif not ai_config.vision_enabled and ai_config.vision_effective_model:
        vision_status = "warning"
        vision_summary = "视觉/OCR 已开启，但缺少 API Key。"
        vision_action = "填写 API Key 后重试图片上传或重新提取。"
    elif not ai_config.vision_effective_model:
        vision_status = "warning"
        vision_summary = "视觉/OCR 已开启，但没有配置视觉模型。"
        vision_action = "在设置里选择或填写支持图片输入的视觉模型。"
    else:
        vision_status = "pass"
        vision_summary = "视觉/OCR 前置配置已满足；真实可用性取决于当前接口是否支持所选视觉模型。"
        vision_action = "如图片上传后仍显示模型调用失败，请检查 Base URL、代理和视觉模型是否属于同一服务。"
    checks.append(
        _check(
            "vision_ocr_config",
            "图片识别/OCR",
            vision_status,
            summary=vision_summary,
            detail=f"enabled={ai_config.enable_vision_ocr}, custom={ai_config.vision_use_custom_config}, base_url={ai_config.vision_effective_base_url or 'default'}, vision_model={ai_config.vision_effective_model}",
            action=vision_action,
            metadata={
                "enable_vision_ocr": ai_config.enable_vision_ocr,
                "vision_use_custom_config": ai_config.vision_use_custom_config,
                "vision_enabled": ai_config.vision_enabled,
                "llm_api_key_configured": ai_config.llm_api_key_configured,
                "vision_api_key_configured": ai_config.vision_api_key_configured,
                "vision_base_url": ai_config.vision_base_url,
                "vision_effective_base_url": ai_config.vision_effective_base_url,
                "vision_model": ai_config.vision_effective_model,
            },
        )
    )

    voice_status = voice_generation_status()
    voice_ready = voice_status.enabled and voice_status.configured
    checks.append(
        _check(
            "voice_adapter",
            "IndexTTS2 声音服务",
            "pass" if voice_ready else "warning",
            summary="IndexTTS2 已开启并配置接口。" if voice_ready else "IndexTTS2 未完全可用，声音预览/朗读会被禁用。",
            detail=f"enabled={voice_status.enabled}, configured={voice_status.configured}, provider={voice_status.provider}, base_url={voice_status.base_url or ''}",
            action="确认 ENABLE_VOICE_GENERATION=true 且 VOICE_GENERATION_BASE_URL 指向可用的 IndexTTS2 adapter。" if not voice_ready else "",
            metadata={
                "enabled": voice_status.enabled,
                "configured": voice_status.configured,
                "provider": voice_status.provider,
                "base_url": voice_status.base_url,
            },
        )
    )
    checks.append(
        _check(
            "ffmpeg_video_audio",
            "视频抽音频",
            "pass" if voice_status.ffmpeg_available else "warning",
            summary="ffmpeg 可用，视频声线参考可以抽取音频。" if voice_status.ffmpeg_available else "ffmpeg 不可用，视频参考不能自动抽音频。",
            detail=voice_status.ffmpeg_path if voice_status.ffmpeg_available else voice_status.ffmpeg_error,
            action="配置 VOICE_VIDEO_FFMPEG_PATH 或把可用 ffmpeg 放到 tools/ffmpeg/ffmpeg.exe。" if not voice_status.ffmpeg_available else "",
            metadata={
                "ffmpeg_path": voice_status.ffmpeg_path,
                "ffmpeg_available": voice_status.ffmpeg_available,
                "video_reference_supported": voice_status.video_reference_supported,
            },
        )
    )

    acceptance_policy = get_feature_policy("acceptance_e2e")
    algorithm_registered = acceptance_policy.algorithm_key in ACCEPTANCE_ALGORITHMS
    checks.append(
        _check(
            "acceptance_policy",
            "核心链路验收",
            "pass" if acceptance_policy.enabled and algorithm_registered else "blocked",
            summary="严苛验收策略已开启，算法已注册。" if acceptance_policy.enabled and algorithm_registered else "严苛验收策略未开启或算法未注册。",
            detail=f"enabled={acceptance_policy.enabled}, algorithm_key={acceptance_policy.algorithm_key}, strictness={acceptance_policy.strictness}",
            action="恢复 acceptance_e2e 策略为 enabled=true 且 algorithm_key=api_smoke_v1。" if not (acceptance_policy.enabled and algorithm_registered) else "",
            metadata={
                "enabled": acceptance_policy.enabled,
                "algorithm_key": acceptance_policy.algorithm_key,
                "algorithm_registered": algorithm_registered,
                "strictness": acceptance_policy.strictness,
            },
        )
    )

    summary = Counter(check.status for check in checks)
    summary["total"] = len(checks)
    return SystemSelfCheckResponse(
        generated_at=_now(),
        app_name=settings.app_name,
        environment=settings.environment,
        api_prefix=settings.api_v1_prefix,
        overall_status=_overall(checks),
        checks=checks,
        required_routes=required_routes,
        summary=dict(summary),
    )
