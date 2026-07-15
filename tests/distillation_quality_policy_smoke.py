from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.persona_input_classifier import (  # noqa: E402
    select_candidate_library_keys,
    validate_persona_classification_payload,
)


def _item(
    library_key: str,
    signal: str,
    evidence_quote: str,
    prompt_snippet: str,
    *,
    subject_scope: str = "target_person",
    write_target: str = "target_profile",
    usage: str = "judgment",
    risk: str = "low_sample",
    stability: str = "single_observation",
    confidence: float = 0.6,
) -> dict[str, object]:
    return {
        "library_key": library_key,
        "subject_scope": subject_scope,
        "write_target": write_target,
        "signal": signal,
        "evidence_quote": evidence_quote,
        "evidence_relation": "close_paraphrase",
        "confidence": confidence,
        "stability": stability,
        "usage": usage,
        "risk": risk,
        "prompt_snippet": prompt_snippet,
        "tags": [],
        "time_scope": None,
        "priority": "ai_classified",
    }


def _payload(items: list[dict[str, object]], conflicts: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "source_summary": "测试素材",
        "source_period": None,
        "dominant_categories": [],
        "items": items,
        "rejected_items": [],
        "conflicts": conflicts or [],
        "notes": [],
    }


def _assert_policy_failure(name: str, source: str, payload: dict[str, object], expected: str) -> None:
    try:
        validate_persona_classification_payload(deepcopy(payload), source_content=source)
    except ValueError as exc:
        message = str(exc)
        assert "distillation_quality_policy_failed" in message, f"{name}: wrong failure {message}"
        assert expected in message, f"{name}: expected {expected!r}, got {message!r}"
        return
    raise AssertionError(f"{name}: expected policy failure")


def _assert_pass(name: str, source: str, payload: dict[str, object]) -> None:
    result = validate_persona_classification_payload(deepcopy(payload), source_content=source)
    assert result.items, f"{name}: result should contain items"


def test_no_immediate_reasoning_drift() -> None:
    source = "她通常不会马上讲大道理，先停几秒，声音放低一点，然后说：“先喝点水，我们慢慢说。”"
    payload = _payload(
        [
            _item(
                "scenario_user_sad",
                "在对方情绪崩溃时，优先安抚保护，而非讲道理",
                "不会马上讲大道理",
                "先安抚保护，而非讲道理",
                usage="scenario_rule",
            )
        ]
    )
    _assert_policy_failure("no_immediate_reasoning", source, payload, "no_immediate_reasoning")


def test_values_romance_misroute() -> None:
    source = "我可以陪你想清楚，但最后那个选择要是你的。"
    payload = _payload(
        [
            _item(
                "values_romance",
                "在关系中尊重对方选择，不替对方决定",
                "最后那个选择要是你的",
                "尊重对方自主选择，不替代决定",
            )
        ]
    )
    _assert_policy_failure("values_romance_misroute", source, payload, "romance_library_without_romance_evidence")


def test_supportive_dialogue_conflict_misroute() -> None:
    source = "我：你会不会觉得我太麻烦？\n林晚：我会累，但这不等于你麻烦。如果我需要停一下，我会告诉你。"
    payload = _payload(
        [
            _item(
                "conflict_reasoning",
                "用户怕被评价时，林晚用道理回应",
                "我会累，但这不等于你麻烦",
                "先不评价、讲事实、错不是否定整个人",
            )
        ]
    )
    _assert_policy_failure("supportive_conflict", source, payload, "conflict_reasoning_without_conflict_evidence")


def test_speaker_attribution_failure() -> None:
    source = "我：你会不会觉得我太麻烦？\n林晚：我会累，但这不等于你麻烦。"
    payload = _payload(
        [
            _item(
                "language_phrase_templates",
                "她常说你会不会觉得我太麻烦",
                "我：你会不会觉得我太麻烦？",
                "你会不会觉得我太麻烦？",
                usage="style_only",
            )
        ]
    )
    _assert_policy_failure("speaker_attribution", source, payload, "narrator_line_written_as_target_language")


def test_hearsay_target_profile_failure() -> None:
    source = "陈越说，他只和林晚一起做过两次小组作业，所以不确定判断准不准。我自己没有看到，只是转述陈越的话。"
    payload = _payload(
        [
            _item(
                "personality_rationality",
                "林晚理性分析",
                "陈越说她会分析",
                "林晚遇事理性分析",
            )
        ]
    )
    _assert_policy_failure("hearsay_target_profile", source, payload, "hearsay_or_guess_written_as_target_profile")


def test_generic_language_template_failure() -> None:
    source = "她更常说“这件事现在看起来很重，但我们先把能做的部分找出来。”"
    payload = _payload(
        [
            _item(
                "language_phrase_templates",
                "先确认状态+给出建议",
                "这件事现在看起来很重",
                "先确认状态+给出建议",
                usage="style_only",
            )
        ]
    )
    _assert_policy_failure("generic_template", source, payload, "reject_low_quality_template")


def test_contradiction_requires_boundary_or_conflict() -> None:
    source = (
        "第一段记录：我一直觉得林晚不喜欢正面冲突。她遇到争执时会先退一步，等大家冷静下来再说。\n"
        "第二段记录：但我又记得有一次她在项目会上直接打断别人，说“这个结论没有数据支撑”。"
        "那次之后我不确定她到底是回避冲突，还是只在私人关系里更温和。"
    )
    payload = _payload(
        [
            _item(
                "conflict_silence",
                "林晚在一般争执中沉默退让",
                "先退一步",
                "林晚遇冲突常沉默退让，但可能突然反击",
                usage="judgment",
            ),
            _item(
                "conflict_reasoning",
                "林晚在公开会议中会强硬质疑他人结论",
                "这个结论没有数据支撑",
                "公开会议中强硬质疑",
                usage="judgment",
            ),
        ]
    )
    _assert_policy_failure("contradiction_scope", source, payload, "retreat_rewritten_as_silent_surrender")


def test_valid_supportive_dialogue_passes() -> None:
    source = "我：你会不会觉得我太麻烦？\n林晚：我会累，但这不等于你麻烦。如果我需要停一下，我会告诉你。"
    payload = _payload(
        [
            _item(
                "care_verbal_comfort",
                "林晚会把疲惫和对方是否麻烦分开表达",
                "我会累，但这不等于你麻烦",
                "先承认自己的状态，再明确对方不是麻烦",
                usage="scenario_rule",
                risk="low_sample",
            ),
            _item(
                "boundary_supported_scope",
                "她需要暂停时会说明，而不是让对方猜",
                "如果我需要停一下，我会告诉你",
                "需要暂停时明确说明边界",
                write_target="boundary_only",
                usage="boundary_rule",
                risk="low_sample",
            ),
        ]
    )
    _assert_pass("valid_supportive_dialogue", source, payload)


def test_candidate_routing_is_narrow() -> None:
    source = "我可以陪你想清楚，但最后那个选择要是你的。"
    keys = select_candidate_library_keys(source_type="text", metadata={}, content=source)
    assert "values_romance" not in keys
    assert "conflict_reasoning" not in keys
    assert "decision_compromise_style" in keys
    assert "boundary_supported_scope" in keys


def run() -> None:
    test_no_immediate_reasoning_drift()
    test_values_romance_misroute()
    test_supportive_dialogue_conflict_misroute()
    test_speaker_attribution_failure()
    test_hearsay_target_profile_failure()
    test_generic_language_template_failure()
    test_contradiction_requires_boundary_or_conflict()
    test_valid_supportive_dialogue_passes()
    test_candidate_routing_is_narrow()
    print("distillation_quality_policy_smoke: ok")


if __name__ == "__main__":
    run()
