"""Button-driven survey UI; the engine owns all survey state."""

import streamlit as st

from questionnaire_chatbot.intent.rule_based import RuleBasedIntentParser
from questionnaire_chatbot.intent.router import route
from questionnaire_chatbot.actions import Action, ActionKind, execute
from questionnaire_chatbot.survey.engine import SurveyEngine, SurveyError
from questionnaire_chatbot.survey.models import QuestionStatus, SurveyStatus
from questionnaire_chatbot.survey.questionnaire import CHOICES, get_question, get_questions

st.set_page_config(page_title="Questionnaire Chatbot Prototype")

LABELS = {choice.code: choice.label for choice in CHOICES}
ACTION_LABELS = {
    ActionKind.START: "설문 시작하기", ActionKind.NEXT: "다음",
    ActionKind.PREVIOUS: "이전", ActionKind.GOTO: "문항으로 이동",
    ActionKind.SKIP: "건너뛰기", ActionKind.REVIEW: "최종 검토",
    ActionKind.RESUME: "설문 계속 작성하기", ActionKind.FINISH: "설문 완료 확정",
    ActionKind.REOPEN: "응답 수정하기",
}

if "survey_engine" not in st.session_state:
    st.session_state.survey_engine = SurveyEngine()
    st.session_state.messages = [("assistant", "안녕하세요! 가상 설문 챗봇입니다. 시작 버튼을 눌러주세요.")]
    st.session_state.ui_version = 0
    st.session_state.notice = None
    st.session_state.last_answered_question = None


def record_result(before, user_text, text, level):
    engine = st.session_state.survey_engine
    st.session_state.notice = (level, text)
    st.session_state.messages.extend([("user", user_text), ("assistant", text)])
    state = engine.state
    if (state.survey_status == SurveyStatus.IN_PROGRESS and
        (before.survey_status != SurveyStatus.IN_PROGRESS or
         before.current_question_index != state.current_question_index)):
        question = get_question(state.current_question_index + 1)
        st.session_state.messages.append(("assistant", f"{question.question_number}번 문항 · {question.question_text}"))


def perform(kind, value, version, natural_text=None):
    """One event path for buttons and natural language; ignore stale events."""
    if version != st.session_state.ui_version:
        return
    st.session_state.ui_version += 1
    engine = st.session_state.survey_engine
    before = engine.state
    user_text = natural_text
    try:
        extra_message = None
        if natural_text is not None:
            parsed = RuleBasedIntentParser().parse(natural_text)
            routed = route(engine, parsed, st.session_state.last_answered_question)
            if routed.action is None:
                record_result(before, natural_text, routed.message, "info")
                return
            kind, value = routed.action.kind, routed.action.value
            extra_message = routed.message
        else:
            if kind == ActionKind.GOTO and value is None:
                value = st.session_state.target_question
            user_text = LABELS.get(value, str(value)) if kind == ActionKind.ANSWER else ACTION_LABELS[kind]
            if kind == ActionKind.GOTO:
                user_text = f"{value}번 문항으로 이동"
        state = execute(engine, Action(kind, value))
        if kind == ActionKind.ANSWER:
            number = state.current_question_index + 1
            st.session_state.last_answered_question = number
            old = before.answers.get(state.current_question_index)
            text = f"{number}번 응답을 ‘{LABELS[value]}’으로 저장했습니다."
            if old == value:
                text = f"{number}번에 동일한 응답이 이미 저장되어 있습니다."
            elif old is not None:
                text = f"{number}번 응답을 ‘{LABELS[old]}’에서 ‘{LABELS[value]}’(으)로 수정했습니다."
        elif state.survey_status == SurveyStatus.REVIEW:
            text = "최종 검토 단계입니다. 응답과 미응답 문항을 확인해주세요. 완료는 ‘설문 완료 확정’ 버튼으로만 확정합니다."
        elif state.survey_status == SurveyStatus.COMPLETED:
            text = "설문이 완료되었습니다. 감사합니다."
        else:
            text = f"{state.current_question_index + 1}번 문항을 표시합니다."
            if kind == ActionKind.SKIP:
                text = f"{before.current_question_index + 1}번 문항을 건너뛰었습니다. " + text
        if extra_message:
            text += " " + extra_message
        level = "success"
    except SurveyError as error:
        text, level = str(error), "warning"
    except Exception:
        text = "작업 처리 중 오류가 발생했습니다. 기존 응답은 유지됩니다. 다시 시도해주세요."
        level = "error"
    record_result(before, user_text, text, level)


def submit_command(version):
    text = st.session_state.command_input
    if text and text.strip():
        perform(None, None, version, natural_text=text)


def action_button(label, kind, value=None, *, key=None, disabled=False, selected=False):
    st.button(label, key=key, disabled=disabled, type="primary" if selected else "secondary",
              use_container_width=True, on_click=perform,
              args=(kind, value, st.session_state.ui_version))


engine = st.session_state.survey_engine
state = engine.state
progress = engine.progress()
st.title("Questionnaire Chatbot")
st.caption("일상생활 활동 경험에 관한 가상 설문 · 총 11문항")
st.write("최근 7일의 경험을 답해주세요. 실제 임상척도와 무관한 시연용 설문이며 점수를 산출하지 않습니다.")
st.caption("응답은 현재 세션에서 유지됩니다. 브라우저 새로고침이나 세션 종료 후에는 복구되지 않습니다.")

st.subheader("설문 진행 상황")
st.write(f"현재 문항 {progress.current_question_index + 1}/{progress.total} · "
         f"응답 {progress.answered} · 건너뜀 {progress.skipped} · 미응답 {progress.unanswered}")
st.progress(progress.processed_fraction, text=f"전체 진행률 {progress.processed_fraction:.0%}")

st.subheader("챗봇 대화")
with st.container(height=300):
    for role, message in st.session_state.messages:
        with st.chat_message(role):
            st.write(message)

if st.session_state.notice:
    level, message = st.session_state.notice
    getattr(st, level)(message)

if state.survey_status == SurveyStatus.NOT_STARTED:
    action_button("설문 시작하기", ActionKind.START)
elif state.survey_status == SurveyStatus.IN_PROGRESS:
    question = get_question(state.current_question_index + 1)
    with st.chat_message("assistant"):
        st.markdown(f"**현재 문항 {question.question_number}/11**")
        st.write(question.question_text)
    answer = engine.get_answer(question.question_number)
    status = engine.question_status(question.question_number)
    st.write(f"저장된 응답: {LABELS[answer]}" if answer else
             "건너뛴 문항입니다. 지금 응답할 수 있습니다." if status == QuestionStatus.SKIPPED else "아직 응답하지 않은 문항입니다.")
    for choice in CHOICES:
        action_button(choice.label, ActionKind.ANSWER, choice.code,
                      key=f"answer_{question.question_number}_{choice.code}", selected=answer == choice.code)
    st.caption("선택 즉시 저장됩니다. 다음 문항으로 자동 이동하지 않습니다.")
    for column, label, kind in zip(st.columns(3), ("이전", "다음", "건너뛰기"),
                                   (ActionKind.PREVIOUS, ActionKind.NEXT, ActionKind.SKIP)):
        with column:
            action_button(label, kind)
    st.selectbox("이동할 문항", options=list(range(1, 12)),
                 format_func=lambda number: f"{number}번 문항", key="target_question")
    action_button("선택 문항으로 이동", ActionKind.GOTO)
    action_button("최종 검토", ActionKind.REVIEW)
else:
    completed = state.survey_status == SurveyStatus.COMPLETED
    st.subheader("설문 완료" if completed else "최종 응답 검토")
    if completed:
        st.success(f"총 {progress.total}문항 중 응답 {progress.answered}개, 건너뜀 {progress.skipped}개로 완료했습니다.")
    rows = []
    status_labels = {QuestionStatus.ANSWERED: "응답 완료", QuestionStatus.SKIPPED: "건너뜀", QuestionStatus.UNANSWERED: "미응답"}
    for question in get_questions():
        number = question.question_number
        rows.append({"번호": number, "질문": question.question_text,
                     "상태": status_labels[engine.question_status(number)],
                     "응답": LABELS.get(engine.get_answer(number), "—")})
    st.table(rows)
    if completed:
        action_button("응답 수정하기", ActionKind.REOPEN)
    else:
        if progress.unanswered:
            st.warning(f"미응답 문항이 {progress.unanswered}개 남아 있어 완료할 수 없습니다.")
        action_button("설문 계속 작성하기", ActionKind.RESUME)
        action_button("설문 완료 확정", ActionKind.FINISH, disabled=progress.unanswered > 0)

st.caption("자연어로 이동·조회·수정을 요청할 수 있습니다. 응답은 선택지 버튼으로 입력해주세요.")
st.chat_input("명령 입력 · 예: 다음 질문으로 넘어가 줘", key="command_input",
              disabled=state.survey_status == SurveyStatus.NOT_STARTED,
              on_submit=submit_command, args=(st.session_state.ui_version,))
