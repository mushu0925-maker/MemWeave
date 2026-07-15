from __future__ import annotations

import re
from dataclasses import dataclass


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(
    r"""
    (?<!\w)
    (?:\+?\d{1,3}[\s.-]?)?
    (?:\(?\d{2,4}\)?[\s.-]?)?
    \d{3,4}[\s.-]?\d{4}
    (?!\w)
    """,
    re.VERBOSE,
)
LABELED_NAME_PATTERN = re.compile(
    r"\b(?:name|full name|client|customer|employee|user|姓名|名字)\s*[:：]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}|[\u4e00-\u9fff]{2,4})",
    re.IGNORECASE,
)
HONORIFIC_NAME_PATTERN = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b"
)


@dataclass(frozen=True)
class PIIMaskingResult:
    content: str
    replacements: dict[str, int]


def mask_pii(raw_content: str) -> PIIMaskingResult:
    """Mask common PII before content is sent to an LLM."""
    replacements = {
        "email": 0,
        "phone": 0,
        "name": 0,
    }

    def replace_email(match: re.Match[str]) -> str:
        replacements["email"] += 1
        return "[EMAIL]"

    def replace_phone(match: re.Match[str]) -> str:
        candidate = match.group(0)
        digit_count = len(re.sub(r"\D", "", candidate))
        if digit_count < 7:
            return candidate
        replacements["phone"] += 1
        return "[PHONE]"

    def replace_labeled_name(match: re.Match[str]) -> str:
        replacements["name"] += 1
        label = match.group(0).split(match.group(1), 1)[0]
        return f"{label}[NAME]"

    def replace_honorific_name(match: re.Match[str]) -> str:
        replacements["name"] += 1
        return "[NAME]"

    content = EMAIL_PATTERN.sub(replace_email, raw_content)
    content = PHONE_PATTERN.sub(replace_phone, content)
    content = LABELED_NAME_PATTERN.sub(replace_labeled_name, content)
    content = HONORIFIC_NAME_PATTERN.sub(replace_honorific_name, content)

    return PIIMaskingResult(content=content, replacements=replacements)
