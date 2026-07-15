from __future__ import annotations

from uuid import UUID

from app.schemas.profile_status import ProfileStage, ProfileStatusResponse
from app.services.ai_config_store import read_ai_config
from app.services.persona_item_store import count_persona_items
from app.services.raw_source_store import count_raw_sources
from app.services.skill_version_store import count_skill_versions, get_latest_skill_version
from app.services.uncertainty_store import count_question_targets, count_uncertain_items


def _stage_for_counts(
    *,
    raw_source_count: int,
    persona_item_count: int,
    open_question_count: int,
    open_uncertain_count: int,
    skill_version_count: int,
    ai_configured: bool,
) -> ProfileStage:
    if not ai_configured:
        return "config_missing"
    if raw_source_count == 0 and persona_item_count == 0:
        if skill_version_count > 0:
            return "skill_saved"
        return "empty"
    if persona_item_count == 0:
        if skill_version_count > 0:
            return "skill_saved"
        return "raw_only"
    if open_question_count > 0 or open_uncertain_count > 0:
        return "needs_confirmation"
    if skill_version_count > 0:
        return "chat_ready"
    return "library_ready"


def _stage_copy(stage: ProfileStage) -> tuple[str, str]:
    copies: dict[ProfileStage, tuple[str, str]] = {
        "config_missing": ("配置缺失", "先到 Settings 测试模型连接，再继续上传、生成 Skill 或聊天。"),
        "empty": ("空档案", "先上传文字、图片、音频或文件，建立 raw_source。"),
        "raw_only": ("只有原数据", "原数据已保存，但还没有可用 A-M 条目；可重新提取或补充资料。"),
        "library_ready": ("A-M 库可用", "可以生成并保存一个 Skill 版本，也可以先去 Library 检查条目。"),
        "needs_confirmation": ("有待确认", "先处理 Library 里的待回答问题或不确定项，再生成更稳的 Skill。"),
        "skill_saved": ("Skill 已保存", "已有保存的 Skill 版本；如果当前 A-M 库为空，先补充或恢复资料后再重新生成。"),
        "chat_ready": ("可聊天", "已有 A-M 库和保存的 Skill 版本，可以进入 Chat 验证效果。"),
    }
    return copies[stage]


def build_profile_status(profile_id: UUID) -> ProfileStatusResponse:
    raw_source_count = count_raw_sources(profile_id)
    persona_item_count = count_persona_items(profile_id)
    open_question_count = count_question_targets(profile_id)
    open_uncertain_count = count_uncertain_items(profile_id)
    skill_version_count = count_skill_versions(profile_id)
    latest_skill_version = get_latest_skill_version(profile_id)
    ai_config = read_ai_config()
    ai_configured = ai_config.llm_enabled and ai_config.enable_ai_classification
    stage = _stage_for_counts(
        raw_source_count=raw_source_count,
        persona_item_count=persona_item_count,
        open_question_count=open_question_count,
        open_uncertain_count=open_uncertain_count,
        skill_version_count=skill_version_count,
        ai_configured=ai_configured,
    )
    stage_label, next_action = _stage_copy(stage)
    warnings: list[str] = []
    if not ai_configured:
        warnings.append("当前模型配置不可用，AI 分类、Skill 生成和聊天可能失败。")
    if open_question_count > 0:
        warnings.append(f"还有 {open_question_count} 个待回答问题。")
    if open_uncertain_count > 0:
        warnings.append(f"还有 {open_uncertain_count} 个不确定项待处理。")
    if persona_item_count == 0 and raw_source_count > 0:
        warnings.append("已有原数据，但还没有可用 A-M 条目。")
    if skill_version_count > 0 and persona_item_count == 0:
        warnings.append("已有 Skill 版本，但当前 A-M 库为空；建议补充或恢复资料后重新生成。")

    return ProfileStatusResponse(
        profile_id=profile_id,
        stage=stage,
        stage_label=stage_label,
        next_action=next_action,
        raw_source_count=raw_source_count,
        persona_item_count=persona_item_count,
        open_question_count=open_question_count,
        open_uncertain_count=open_uncertain_count,
        skill_version_count=skill_version_count,
        latest_skill_version_id=latest_skill_version.id if latest_skill_version else None,
        ai_configured=ai_configured,
        can_generate_skill=persona_item_count > 0,
        can_chat=persona_item_count > 0 and ai_config.llm_enabled,
        warnings=warnings,
    )
