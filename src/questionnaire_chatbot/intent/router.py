"""Validate parser results and resolve references without mutating survey state.

FINISH requests route only to REVIEW; final confirmation remains a UI button.
"""
from dataclasses import dataclass

from ..actions import Action, ActionKind
from ..survey.engine import SurveyEngine, SurveyError
from ..survey.models import QuestionStatus, SurveyStatus
from ..survey.questionnaire import CHOICES
from .schemas import Intent, ParseResult, ParseStatus, TargetReference


@dataclass(frozen=True)
class Route:
    action: Action | None = None
    message: str | None = None


def route(engine: SurveyEngine, parsed: ParseResult, last_answered: int | None) -> Route:
    state = engine.state
    if state.survey_status == SurveyStatus.NOT_STARTED:
        raise SurveyError("먼저 ‘설문 시작하기’ 버튼을 눌러주세요.")
    if parsed.status != ParseStatus.MATCHED:
        messages = {
            ParseStatus.UNKNOWN: "지원하지 않는 명령입니다. 예: ‘다음 질문으로 넘어가 줘’. 응답은 선택지 버튼으로 입력해주세요.",
            ParseStatus.AMBIGUOUS: "어떤 작업인지 명확하게 한 번에 하나씩 입력해주세요. 예: ‘2번 질문으로 이동해 줘’.",
            ParseStatus.REJECTED: "부정 명령 또는 유효하지 않은 문항 번호이므로 실행하지 않았습니다.",
        }
        return Route(message=messages[parsed.status])
    if parsed.intent == Intent.PROGRESS:
        p = engine.progress()
        return Route(message=f"현재 {p.current_question_index + 1}/{p.total}번 문항 · 응답 {p.answered}개 · 건너뜀 {p.skipped}개 · 미응답 {p.unanswered}개 · 진행률 {p.processed_fraction:.0%}")

    def target():
        if parsed.target_question is not None:
            number = parsed.target_question
        elif parsed.target_reference == TargetReference.CURRENT:
            number = state.current_question_index + 1
        elif parsed.target_reference == TargetReference.PREVIOUS:
            number = state.current_question_index
        elif parsed.target_reference == TargetReference.LAST_ANSWER and last_answered is not None:
            number = last_answered
        else:
            raise SurveyError("대상 문항을 확인할 수 없습니다. 문항 번호를 명시해주세요.")
        engine.question_status(number)  # Validate 1..11, including previous of first.
        return number

    if parsed.intent == Intent.SHOW_ANSWER:
        number = target()
        status = engine.question_status(number)
        if status == QuestionStatus.UNANSWERED:
            text = "아직 응답하지 않은 문항입니다."
        elif status == QuestionStatus.SKIPPED:
            text = "건너뛴 문항입니다."
        else:
            labels = {choice.code: choice.label for choice in CHOICES}
            text = f"저장된 응답은 ‘{labels[engine.get_answer(number)]}’입니다."
        return Route(message=f"{number}번: {text}")
    if state.survey_status == SurveyStatus.COMPLETED:
        raise SurveyError("완료된 설문입니다. ‘응답 수정하기’ 버튼으로 수정 모드에 진입해주세요.")
    if state.survey_status == SurveyStatus.REVIEW:
        if parsed.intent in (Intent.FINISH, Intent.REVIEW):
            return Route(message="최종 검토 중입니다. 미응답을 처리한 뒤 ‘설문 완료 확정’ 버튼을 눌러주세요.")
        raise SurveyError("최종 검토 중입니다. ‘설문 계속 작성하기’ 버튼을 눌러주세요.")
    if parsed.intent == Intent.EDIT:
        number = target()
        if engine.question_status(number) != QuestionStatus.ANSWERED:
            raise SurveyError("저장된 응답이 없는 문항입니다. 문항 번호로 이동한 뒤 선택지로 응답해주세요.")
        message = "기존 응답은 유지됩니다. 선택지 버튼을 눌러 새 응답을 저장해주세요."
        if number == state.current_question_index + 1:
            return Route(message=message)
        return Route(Action(ActionKind.GOTO, number), message)
    if parsed.intent in (Intent.FINISH, Intent.REVIEW):
        return Route(Action(ActionKind.REVIEW))
    mapping = {Intent.NEXT: ActionKind.NEXT, Intent.PREVIOUS: ActionKind.PREVIOUS,
               Intent.SKIP: ActionKind.SKIP, Intent.GOTO: ActionKind.GOTO}
    if parsed.intent in mapping:
        return Route(Action(mapping[parsed.intent], parsed.target_question if parsed.intent == Intent.GOTO else None))
    raise SurveyError("지원하지 않는 명령입니다.")
