from __future__ import annotations

from app.schemas.persona_item import LibraryGroup, PersonaItemStatus

CATEGORY_TO_GROUP: dict[str, LibraryGroup] = {
    "fact_memory": "A",
    "language_style": "B",
    "emotion_response": "C",
    "personality_traits": "D",
    "values_worldview": "E",
    "relationship_modes": "F",
    "decision_logic": "G",
    "conflict_defense": "H",
    "care_companionship": "I",
    "scenario_response": "J",
    "growth_change": "K",
    "boundary_confidence": "L",
    "voice_speech_feature": "M",
}


def library_group_from_category(category: str, library_key: str) -> LibraryGroup:
    if library_key.startswith("voice_"):
        return "M"
    return CATEGORY_TO_GROUP.get(category, "L")


def status_from_classification(*, write_target: str, risk: str, confidence: float, stability: str) -> PersonaItemStatus:
    if write_target == "rejected_until_confirmed":
        return "rejected_until_confirmed"
    if risk in {"sensitive", "safety_boundary", "conflict", "unsupported_fact", "over_intimacy", "impersonation"}:
        return "candidate"
    if confidence < 0.5 or stability in {"single_observation", "candidate", "unknown", "conflict"}:
        return "candidate"
    return "active"
