"""Temporary independent demo content, unrelated to clinical scales.

Replace question_text values here when wording is finalized. Stable one-based
numbers connect content to the engine; no survey state is read or modified.
Choices are ordered for display and carry no scores or weights.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    question_number: int
    question_text: str


@dataclass(frozen=True)
class Choice:
    code: str
    label: str


QUESTIONS: tuple[Question, ...] = (
    Question(1, "최근 7일 동안 좋아하는 음악을 얼마나 자주 들었나요?"),
    Question(2, "최근 7일 동안 책이나 기사를 얼마나 자주 읽었나요?"),
    Question(3, "최근 7일 동안 산책을 얼마나 자주 했나요?"),
    Question(4, "최근 7일 동안 영화나 영상을 얼마나 자주 시청했나요?"),
    Question(5, "최근 7일 동안 하루 일정을 얼마나 자주 정리했나요?"),
    Question(6, "최근 7일 동안 음식이나 간식을 얼마나 자주 만들었나요?"),
    Question(7, "최근 7일 동안 주변 사람들과 안부를 얼마나 자주 나누었나요?"),
    Question(8, "최근 7일 동안 취미 활동을 얼마나 자주 했나요?"),
    Question(9, "최근 7일 동안 생활공간을 얼마나 자주 정리했나요?"),
    Question(10, "최근 7일 동안 궁금한 정보를 얼마나 자주 찾아보았나요?"),
    Question(11, "최근 7일 동안 하루를 되돌아보는 시간을 얼마나 자주 가졌나요?"),
)

CHOICES: tuple[Choice, ...] = (
    Choice("NEVER", "전혀 하지 않음"),
    Choice("RARELY", "드물게"),
    Choice("SOMETIMES", "가끔"),
    Choice("OFTEN", "자주"),
    Choice("UNSURE_OR_NA", "모르겠음·해당 없음"),
)


def get_questions() -> tuple[Question, ...]:
    """Return all questions in display order as immutable records."""
    return QUESTIONS


def get_question(question_number: int) -> Question:
    """Look up a one-based question number; reject bools and non-integers."""
    if type(question_number) is not int:
        raise ValueError("문항 번호는 1~11의 정수여야 합니다.")
    for question in QUESTIONS:
        if question.question_number == question_number:
            return question
    raise ValueError("존재하지 않는 문항 번호입니다. 1~11을 입력해주세요.")
