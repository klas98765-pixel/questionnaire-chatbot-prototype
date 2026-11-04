"""Parser results only; no execution or survey state dependencies."""

from dataclasses import dataclass
from enum import Enum


class Intent(str, Enum):
    NEXT = "NEXT"
    PREVIOUS = "PREVIOUS"
    SKIP = "SKIP"
    EDIT = "EDIT"
    GOTO = "GOTO"
    PROGRESS = "PROGRESS"
    SHOW_ANSWER = "SHOW_ANSWER"
    REVIEW = "REVIEW"
    FINISH = "FINISH"
    UNKNOWN = "UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"
    REJECTED = "REJECTED"


class TargetReference(str, Enum):
    CURRENT = "CURRENT"
    PREVIOUS = "PREVIOUS"
    LAST_ANSWER = "LAST_ANSWER"


class ParseStatus(str, Enum):
    MATCHED = "MATCHED"
    UNKNOWN = "UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ParseResult:
    intent: Intent
    target_question: int | None
    target_reference: TargetReference | None
    original_text: str
    status: ParseStatus
