"""Real Streamlit script integration using button events and session reruns."""
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from questionnaire_chatbot.actions import Action, ActionKind, execute
from questionnaire_chatbot.survey.engine import SurveyEngine, SurveyError
from questionnaire_chatbot.survey.models import SurveyStatus


class AppTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
        self.assertFalse(self.app.exception)

    def click(self, label):
        next(button for button in self.app.button if button.label == label).click().run()
        self.assertFalse(self.app.exception)

    @property
    def engine(self):
        return self.app.session_state['survey_engine']

    def goto(self, number):
        self.app.selectbox[0].select(number).run()
        self.click('선택 문항으로 이동')

    def test_start_and_rerun_without_duplicate_messages(self):
        self.click('설문 시작하기')
        self.assertEqual(self.engine.state.current_question_index, 0)
        self.assertIn('좋아하는 음악', self.app.chat_message[-1].markdown[-1].value)
        messages = list(self.app.session_state['messages'])
        self.app.run()
        self.assertEqual(self.app.session_state['messages'], messages)
        self.assertTrue(self.app.chat_input[0].disabled)

    def test_navigation_edit_skip_and_progress(self):
        self.click('설문 시작하기')
        before = self.engine.state
        self.click('다음')
        self.assertEqual(self.engine.state, before)
        self.assertTrue(self.app.warning)
        self.click('이전')
        self.assertEqual(self.engine.state, before)
        self.click('가끔')
        self.assertEqual(self.engine.get_answer(1), 'SOMETIMES')
        self.assertEqual(self.engine.state.current_question_index, 0)
        before = self.engine.state
        self.click('건너뛰기')
        self.assertEqual(self.engine.state, before)
        self.click('다음')
        self.click('이전')
        self.assertEqual(self.engine.get_answer(1), 'SOMETIMES')
        self.click('자주')
        self.assertEqual(self.engine.get_answer(1), 'OFTEN')
        self.goto(3)
        self.click('건너뛰기')
        self.assertIn(2, self.engine.state.skipped_questions)
        self.goto(3)
        self.click('드물게')
        self.assertNotIn(2, self.engine.state.skipped_questions)
        self.assertEqual(self.engine.progress().answered, 2)
        self.app.run()
        self.assertEqual(self.engine.get_answer(3), 'RARELY')

    def test_review_block_and_resume(self):
        self.click('설문 시작하기')
        self.goto(11)
        self.click('모르겠음·해당 없음')
        self.click('다음')
        self.assertEqual(self.engine.state.survey_status, SurveyStatus.REVIEW)
        self.assertTrue(next(b for b in self.app.button if b.label == '설문 완료 확정').disabled)
        self.assertEqual(len(self.app.table[0].value), 11)
        self.click('설문 계속 작성하기')
        self.assertEqual(self.engine.state.current_question_index, 0)

    def test_all_eleven_complete_and_reopen(self):
        self.click('설문 시작하기')
        for number in range(1, 12):
            self.assertEqual(self.engine.state.current_question_index, number - 1)
            self.click('가끔')
            self.click('다음')
        self.assertEqual(self.engine.state.survey_status, SurveyStatus.REVIEW)
        self.click('설문 완료 확정')
        self.assertEqual(self.engine.state.survey_status, SurveyStatus.COMPLETED)
        self.assertEqual(len(self.app.table[0].value), 11)
        self.assertNotIn('가끔', [b.label for b in self.app.button])
        self.click('응답 수정하기')
        self.click('자주')
        self.assertEqual(self.engine.get_answer(1), 'OFTEN')
        self.click('최종 검토')
        self.click('설문 완료 확정')
        self.assertEqual(self.engine.progress().answered, 11)

    def test_duplicate_event_is_ignored(self):
        script = (Path(__file__).resolve().parents[1] / 'app.py').read_text()
        script += "\nif st.session_state.get('replay_version') is not None:\n    perform(ActionKind.NEXT, None, st.session_state.replay_version)\n"
        self.app = AppTest.from_string(script, default_timeout=15).run()
        self.click('설문 시작하기')
        self.click('가끔')
        version = self.app.session_state['ui_version']
        self.click('다음')
        self.click('드물게')
        snapshot = self.engine.state
        messages = list(self.app.session_state['messages'])
        self.app.session_state['replay_version'] = version
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.engine.state, snapshot)
        self.assertEqual(self.app.session_state['messages'], messages)

    def test_unexpected_error_shows_message_and_keeps_state(self):
        self.click('설문 시작하기')
        before = self.engine.state
        with patch.object(SurveyEngine, 'save_answer', side_effect=RuntimeError('test')):
            self.click('가끔')
        self.assertEqual(self.engine.state, before)
        self.assertTrue(self.app.error)


class DispatcherTests(unittest.TestCase):
    def test_invalid_and_completed_actions_preserve_state(self):
        engine = SurveyEngine()
        execute(engine, Action(ActionKind.START))
        before = engine.state
        for action in (Action(ActionKind.GOTO, 12), Action(ActionKind.ANSWER, 'bad'), Action('invalid')):
            with self.assertRaises(SurveyError):
                execute(engine, action)
            self.assertEqual(engine.state, before)
        for _ in range(11):
            execute(engine, Action(ActionKind.SKIP))
        execute(engine, Action(ActionKind.FINISH))
        before = engine.state
        with self.assertRaises(SurveyError):
            execute(engine, Action(ActionKind.ANSWER, 'OFTEN'))
        self.assertEqual(engine.state, before)
