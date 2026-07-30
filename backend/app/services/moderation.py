import re
from collections.abc import Mapping, Sequence
from typing import Any


_PROFANITY_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b[а-яё]*бля(?:д|т)[а-яё]*\b",
        r"\b[а-яё]*п[иеё]зд[а-яё]*\b",
        r"\b[а-яё]*х[уy][йяеёиюи][а-яё]*\b",
        r"\b(?:за|на|по|вы|про|при|разъ|раз|съ|от|до)?(?:е|ё)б(?:а|и|у|л|н|о|ё|ы|с|т|уч)[а-яё]*\b",
    )
]


def censor_text(value: str) -> str:
    censored = value
    for pattern in _PROFANITY_PATTERNS:
        censored = pattern.sub(lambda match: "*" * len(match.group(0)), censored)
    return censored


def censor_content(value: Any) -> Any:
    if isinstance(value, str):
        return censor_text(value)
    if isinstance(value, Mapping):
        return {key: censor_content(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [censor_content(item) for item in value]
    return value
