"""Structured button actions; no natural-language parsing or UI dependencies."""

from dataclasses import dataclass
from enum import Enum

from .survey.engine import SurveyEngine, SurveyError
from .survey.models import SurveyState


class ActionKind(str, Enum):
    START = "START"
    ANSWER = "ANSWER"
    NEXT = "NEXT"
    PREVIOUS = "PREVIOUS"
    GOTO = "GOTO"
    SKIP = "SKIP"
    REVIEW = "REVIEW"
    RESUME = "RESUME"
    FINISH = "FINISH"
    REOPEN = "REOPEN"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    value: str | int | None = None


def execute(engine: SurveyEngine, action: Action) -> SurveyState:
    """Delegate transitions to the engine, which remains the source of truth."""
    if not isinstance(action, Action) or not isinstance(action.kind, ActionKind):
        raise SurveyError("지원하지 않는 작업입니다.")
    if action.kind == ActionKind.ANSWER:
        return engine.save_answer(action.value)
    if action.kind == ActionKind.GOTO:
        return engine.goto_question(action.value)
    if action.value is not None:
        raise SurveyError("이 작업에는 추가 값이 필요하지 않습니다.")
    handlers = {
        ActionKind.START: engine.start,
        ActionKind.NEXT: engine.next_question,
        ActionKind.PREVIOUS: engine.previous_question,
        ActionKind.SKIP: engine.skip_question,
        ActionKind.REVIEW: engine.request_review,
        ActionKind.RESUME: engine.resume,
        ActionKind.FINISH: engine.finish,
        ActionKind.REOPEN: engine.reopen_for_edit,
    }
    return handlers[action.kind]()
