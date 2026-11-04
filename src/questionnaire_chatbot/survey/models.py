"""Survey state without UI dependencies or question wording.

Indexes are zero-based (0..10); user-facing question numbers are 1..11.
Answer values are stable choice codes, never clinical scores.
"""

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

QUESTION_COUNT = 11
CHOICE_CODES = frozenset({"NEVER", "RARELY", "SOMETIMES", "OFTEN", "UNSURE_OR_NA"})


class QuestionStatus(str, Enum):
    UNANSWERED = "UNANSWERED"
    ANSWERED = "ANSWERED"
    SKIPPED = "SKIPPED"


class SurveyStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    COMPLETED = "COMPLETED"


@dataclass
class SurveyState:
    session_id: str = field(default_factory=lambda: str(uuid4()))
    current_question_index: int = 0
    answers: dict[int, str] = field(default_factory=dict)
    skipped_questions: set[int] = field(default_factory=set)
    survey_status: SurveyStatus = SurveyStatus.NOT_STARTED
    last_action: str | None = None
