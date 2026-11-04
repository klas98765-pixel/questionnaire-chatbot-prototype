# Questionnaire Chatbot Prototype

가상 설문 11문항을 사용하는 대화형 웹 프로토타입을 위한 독립 Python 프로젝트입니다.
향후 문항 이동, 응답 선택 및 수정, 최종 확인 기능을 구현할 예정입니다.
현재는 개발 환경과 폴더 구조만 준비했으며 설문 문항과 챗봇 동작은 구현하지 않았습니다.

## 실행환경

- Python 3.11 이상 (현재 환경은 Python 3.11의 `.venv`)
- 최소 런타임 의존성: Streamlit (`pyproject.toml` 참고)
- 외부 API, API 키, 원본 데이터는 필요하지 않습니다.

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

실행하면 개발 준비 상태를 알리는 정적 화면만 표시됩니다.

## 구조

```text
app.py                             Streamlit 진입점
src/questionnaire_chatbot/
  intent/base.py                   분류기 Protocol 인터페이스
  survey/                          가상 문항·응답·이동 상태 구현 예정
tests/                            향후 테스트 위치
data/                             Git 제외 로컬 데이터 위치
requirements.txt                   프로젝트 설치 진입점
pyproject.toml                     패키지 및 최소 의존성 정의
```

의도 분류기는 `IntentClassifier` 계약을 통해 향후 Rule-based, ML, LLM 구현을
교체할 수 있도록 준비했습니다. 현재 분류기 구현이나 라우팅 기능은 없습니다.
가상 11문항은 추후 자체 작성하며 실제 K-IADL 문항은 사용하지 않습니다.

## 데이터 및 Git 관리

이 폴더의 `.git`은 기존 Plan C와 별도의 로컬 저장소입니다.
`~/planc_codex_work`는 사용하거나 수정하지 않습니다.
AI Hub 및 3i4K 원본 데이터는 복사하지 않습니다.
`.venv`, `.env`, 비밀키, 개인정보용 폴더, 로컬 데이터, 실행 결과는
`.gitignore`로 제외합니다. 개인정보나 비밀값을 소스 파일에 직접 넣지 마세요.
원격 저장소 생성 및 push는 수행하지 않습니다.

## 기본 검증

```sh
.venv/bin/python -m pip check
.venv/bin/python -c "import streamlit, questionnaire_chatbot; print(streamlit.__version__)"
```
