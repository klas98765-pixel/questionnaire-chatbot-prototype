"""Static chatbot UI preview; no survey state or command handling."""

import streamlit as st

st.set_page_config(page_title="Questionnaire Chatbot Prototype")
st.title("Questionnaire Chatbot")
st.caption("가상 설문 챗봇 프로토타입 · 기본 화면 미리보기")
st.write(
    "대화하며 가상 설문에 응답하는 화면입니다. "
    "실제 환자정보나 임상척도를 사용하지 않습니다."
)
st.info(
    "현재는 UI 미리보기입니다. 응답 저장, 문항 이동, 건너뛰기와 "
    "자연어 명령 처리는 아직 구현되지 않아 모든 조작이 비활성화되어 있습니다."
)

st.subheader("설문 진행 상황")
st.progress(0, text="진행률 0% · 예시 화면 (실제 설문 미시작)")
st.caption("현재 표시: 임시 예시 문항 1개 · 향후 설문: 총 11문항")

st.subheader("챗봇 대화")
with st.chat_message("assistant"):
    st.write("안녕하세요! 가상 설문 챗봇입니다. 아래는 화면 구성을 확인하기 위한 예시 질문입니다.")
with st.chat_message("assistant"):
    st.markdown("**임시 예시 문항**")
    st.write("최근 7일 동안 좋아하는 음악을 얼마나 자주 들었나요?")
    st.caption("확정된 설문 문항이 아닌 UI 확인용 예시입니다.")

st.subheader("응답 선택")
st.caption("선택지는 표시만 됩니다. 응답은 저장되지 않습니다.")
for label in (
    "① 전혀 하지 않음",
    "② 드물게",
    "③ 가끔",
    "④ 자주",
    "⑤ 모르겠음·해당 없음",
):
    st.button(label, disabled=True, use_container_width=True)

previous, following, skip = st.columns(3)
with previous:
    st.button("이전", disabled=True, use_container_width=True)
with following:
    st.button("다음", disabled=True, use_container_width=True)
with skip:
    st.button("건너뛰기", disabled=True, use_container_width=True)

st.caption("자연어 명령 입력도 준비 중입니다. 예: ‘다음 질문으로 넘어가 줘.’")
st.chat_input("자연어 명령 입력 (아직 사용할 수 없습니다)", disabled=True)
