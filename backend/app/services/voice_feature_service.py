from __future__ import annotations

import re

from app.schemas.clarification import QuestionTargetCreate, QuestionTargetSchema
from app.schemas.raw_source import RawSourceSchema
from app.services.uncertainty_store import save_question_target

VOICE_FEATURE_LIBRARY_KEY = "voice_speech_features"


def build_voice_feature_metadata(
    *,
    transcript: str,
    notes: str,
    asr_status: str,
) -> dict[str, str | int | float | bool | None]:
    text = f"{transcript}\n{notes}".strip()
    descriptors: list[str] = []
    if re.search(r"[!?！？]{2,}", text):
        descriptors.append("可能有较强语气或情绪起伏，需要用户确认")
    if re.search(r"(\.{3,}|…|——|--)", text):
        descriptors.append("可能存在停顿、拖长或迟疑表达，需要用户确认")
    if re.search(r"(哈+|嘿+|嗯+|唔+|啊+|呀+|啦+|嘛+|吧)", text):
        descriptors.append("可能包含口头语、语气词或轻声互动习惯，需要用户确认")
    if re.search(r"\n.{1,20}\n", f"\n{text}\n"):
        descriptors.append("可能偏短句或分行表达，需要结合更多音频确认")
    if not descriptors:
        descriptors.append("需要用户从语速、停顿、语气、口头语和互动节奏补充描述")
    return {
        "voice_feature_entry": True,
        "voice_feature_library_group": "M",
        "voice_feature_library_key": VOICE_FEATURE_LIBRARY_KEY,
        "voice_feature_status": "candidate_needs_confirmation",
        "voice_feature_summary": "；".join(descriptors),
        "voice_feature_safety": (
            "Descriptive speech/voice traits only. This is not voice cloning, "
            "not a speaker impersonation recipe, and not clone-ready acoustic parameters."
        ),
        "asr_status": asr_status,
    }


def create_voice_feature_question(raw_source: RawSourceSchema) -> QuestionTargetSchema | None:
    if raw_source.profile_id is None or raw_source.source_type != "audio":
        return None
    metadata = raw_source.metadata
    if not metadata.get("voice_feature_entry"):
        return None
    summary_text = str(metadata.get("voice_feature_summary") or "")
    return save_question_target(
        QuestionTargetCreate(
            profile_id=raw_source.profile_id,
            source_id=raw_source.id,
            target_group="M",
            target_library_key=VOICE_FEATURE_LIBRARY_KEY,
            reason="needs_example",
            question=(
                "这段音频里有哪些只用于描述的说话特征？请从语速、停顿、语气、口头语、"
                "互动节奏中选择有证据的部分说明。不要提供声线克隆、模仿或冒充指令。"
            ),
            example_answer=summary_text[:500],
            priority=74,
            expected_evidence_type="descriptive_voice_or_speech_trait",
            metadata={
                "source": "audio_upload_voice_feature_entry",
                "safety": metadata.get("voice_feature_safety", ""),
                "asr_status": metadata.get("asr_status", ""),
            },
        )
    )
