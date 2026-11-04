"""Transactional, in-memory survey engine.

Every mutation runs on a deep copy and commits only after validation.
Public state and query results are snapshots, not mutable engine internals.
Rejected operations raise SurveyError without changing any saved state.
"""

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

from .models import CHOICE_CODES, QUESTION_COUNT, QuestionStatus, SurveyState, SurveyStatus


class SurveyError(ValueError):
    """Invalid command, argument, lifecycle transition, or state."""


def _index(value: int) -> None:
    if type(value) is not int or not 0 <= value < QUESTION_COUNT:
        raise SurveyError("문항 인덱스는 0~10의 정수여야 합니다.")


def validate_state(state: SurveyState) -> None:
    """Check all invariants before accepting a candidate state."""
    if not isinstance(state, SurveyState):
        raise SurveyError("설문 상태 형식이 올바르지 않습니다.")
    if not isinstance(state.session_id, str) or not state.session_id.strip():
        raise SurveyError("세션 식별자가 필요합니다.")
    _index(state.current_question_index)
    if not isinstance(state.survey_status, SurveyStatus):
        raise SurveyError("설문 진행 상태가 올바르지 않습니다.")
    if not isinstance(state.answers, dict) or not isinstance(state.skipped_questions, set):
        raise SurveyError("응답 및 건너뜀 저장 형식이 올바르지 않습니다.")
    for index, answer in state.answers.items():
        _index(index)
        if not isinstance(answer, str) or answer not in CHOICE_CODES:
            raise SurveyError("유효한 응답 코드를 선택해주세요.")
    for index in state.skipped_questions:
        _index(index)
    if set(state.answers) & state.skipped_questions:
        raise SurveyError("응답과 건너뜀 상태는 중복될 수 없습니다.")
    if state.last_action is not None and not isinstance(state.last_action, str):
        raise SurveyError("마지막 작업 형식이 올바르지 않습니다.")
    if state.survey_status == SurveyStatus.NOT_STARTED and (
        state.answers or state.skipped_questions or state.current_question_index != 0
    ):
        raise SurveyError("시작 전 상태에 응답이나 이동 기록이 있습니다.")
    if state.survey_status == SurveyStatus.COMPLETED and (
        len(state.answers) + len(state.skipped_questions) != QUESTION_COUNT
    ):
        raise SurveyError("미응답 문항이 있어 완료할 수 없습니다.")


@dataclass(frozen=True)
class Progress:
    current_question_index: int
    total: int
    answered: int
    skipped: int
    unanswered: int
    processed_fraction: float
    survey_status: SurveyStatus


class SurveyEngine:
    def __init__(self, state: SurveyState | None = None):
        candidate = deepcopy(state) if state is not None else SurveyState()
        validate_state(candidate)
        self._state = candidate

    @property
    def state(self) -> SurveyState:
        return deepcopy(self._state)

    def _apply(self, action: str, operation: Callable[[SurveyState], None]) -> SurveyState:
        candidate = deepcopy(self._state)
        operation(candidate)
        candidate.last_action = action
        validate_state(candidate)
        self._state = candidate
        return self.state

    @staticmethod
    def _require(state: SurveyState, status: SurveyStatus) -> None:
        if state.survey_status != status:
            raise SurveyError("현재 설문 단계에서 실행할 수 없는 작업입니다.")

    def start(self) -> SurveyState:
        def operation(state):
            self._require(state, SurveyStatus.NOT_STARTED)
            state.survey_status = SurveyStatus.IN_PROGRESS
        return self._apply("START", operation)

    def save_answer(self, answer: str) -> SurveyState:
        """Save or replace the current answer without navigating."""
        def operation(state):
            self._require(state, SurveyStatus.IN_PROGRESS)
            if not isinstance(answer, str) or answer not in CHOICE_CODES:
                raise SurveyError("유효한 응답 코드를 선택해주세요.")
            state.answers[state.current_question_index] = answer
            state.skipped_questions.discard(state.current_question_index)
        return self._apply("SAVE_ANSWER", operation)

    def next_question(self) -> SurveyState:
        def operation(state):
            self._require(state, SurveyStatus.IN_PROGRESS)
            index = state.current_question_index
            if index not in state.answers and index not in state.skipped_questions:
                raise SurveyError("응답을 선택하거나 건너뛰기를 실행해주세요.")
            if index == QUESTION_COUNT - 1:
                state.survey_status = SurveyStatus.REVIEW
            else:
                state.current_question_index += 1
        return self._apply("NEXT", operation)

    def previous_question(self) -> SurveyState:
        def operation(state):
            self._require(state, SurveyStatus.IN_PROGRESS)
            if state.current_question_index == 0:
                raise SurveyError("첫 번째 문항입니다.")
            state.current_question_index -= 1
        return self._apply("PREVIOUS", operation)

    def goto_question(self, question_number: int) -> SurveyState:
        """Accept a one-based user-facing question number (1..11)."""
        def operation(state):
            self._require(state, SurveyStatus.IN_PROGRESS)
            if type(question_number) is not int or not 1 <= question_number <= QUESTION_COUNT:
                raise SurveyError("문항 번호는 1~11의 정수여야 합니다.")
            state.current_question_index = question_number - 1
        return self._apply("GOTO", operation)

    def skip_question(self) -> SurveyState:
        def operation(state):
            self._require(state, SurveyStatus.IN_PROGRESS)
            index = state.current_question_index
            if index in state.answers:
                raise SurveyError("이미 저장된 응답은 건너뛰기로 삭제할 수 없습니다.")
            state.skipped_questions.add(index)
            if index == QUESTION_COUNT - 1:
                state.survey_status = SurveyStatus.REVIEW
            else:
                state.current_question_index += 1
        return self._apply("SKIP", operation)

    def request_review(self) -> SurveyState:
        def operation(state):
            self._require(state, SurveyStatus.IN_PROGRESS)
            state.survey_status = SurveyStatus.REVIEW
        return self._apply("REVIEW", operation)

    def resume(self) -> SurveyState:
        """Leave review, targeting the first unanswered question if one exists."""
        def operation(state):
            self._require(state, SurveyStatus.REVIEW)
            for index in range(QUESTION_COUNT):
                if index not in state.answers and index not in state.skipped_questions:
                    state.current_question_index = index
                    break
            state.survey_status = SurveyStatus.IN_PROGRESS
        return self._apply("RESUME", operation)

    def finish(self) -> SurveyState:
        def operation(state):
            self._require(state, SurveyStatus.REVIEW)
            state.survey_status = SurveyStatus.COMPLETED
        return self._apply("FINISH", operation)

    def reopen_for_edit(self) -> SurveyState:
        def operation(state):
            self._require(state, SurveyStatus.COMPLETED)
            state.survey_status = SurveyStatus.IN_PROGRESS
            state.current_question_index = 0
        return self._apply("REOPEN_FOR_EDIT", operation)

    def question_status(self, question_number: int) -> QuestionStatus:
        if type(question_number) is not int or not 1 <= question_number <= QUESTION_COUNT:
            raise SurveyError("문항 번호는 1~11의 정수여야 합니다.")
        index = question_number - 1
        if index in self._state.answers:
            return QuestionStatus.ANSWERED
        if index in self._state.skipped_questions:
            return QuestionStatus.SKIPPED
        return QuestionStatus.UNANSWERED

    def get_answer(self, question_number: int) -> str | None:
        self.question_status(question_number)  # Validate before lookup.
        return self._state.answers.get(question_number - 1)

    def progress(self) -> Progress:
        state = self._state
        answered, skipped = len(state.answers), len(state.skipped_questions)
        return Progress(state.current_question_index, QUESTION_COUNT, answered, skipped,
                        QUESTION_COUNT - answered - skipped,
                        (answered + skipped) / QUESTION_COUNT, state.survey_status)

    def summary(self) -> list[dict]:
        return [{"question_number": number, "status": self.question_status(number),
                 "answer": self.get_answer(number)}
                for number in range(1, QUESTION_COUNT + 1)]
