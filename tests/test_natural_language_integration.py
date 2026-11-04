"""Natural-language events through real Streamlit callbacks and the engine."""
from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from questionnaire_chatbot.survey.models import SurveyStatus
from questionnaire_chatbot.intent.rule_based import RuleBasedIntentParser
from questionnaire_chatbot.intent.router import route


class NaturalLanguageTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
        self.click('설문 시작하기')

    @property
    def engine(self):
        return self.app.session_state['survey_engine']

    def click(self, label):
        next(b for b in self.app.button if b.label == label).click().run()
        self.assertFalse(self.app.exception)

    def say(self, text):
        self.app.chat_input[0].set_value(text).run()
        self.assertFalse(self.app.exception)

    def reply(self):
        return self.app.session_state['notice'][1]

    def unchanged(self, text):
        before = self.engine.state
        self.say(text)
        self.assertEqual(self.engine.state, before)

    def test_next(self):
        self.click('가끔'); self.say('다음 질문으로 넘어가 줘')
        self.assertEqual(self.engine.state.current_question_index, 1)

    def test_unanswered_next(self):
        self.unchanged('다음 질문으로 넘어가 줘')
        self.assertIn('응답', self.reply())

    def test_previous(self):
        self.say('3번 질문으로 이동해 줘'); self.say('이전 질문 보여줘')
        self.assertEqual(self.engine.state.current_question_index, 1)

    def test_first_previous(self):
        self.unchanged('이전 질문 보여줘')
        self.assertIn('첫 번째', self.reply())

    def test_skip(self):
        self.say('이 질문은 건너뛸게')
        self.assertEqual(self.engine.state.skipped_questions, {0})
        self.assertEqual(self.engine.state.current_question_index, 1)

    def test_goto_and_selectbox_disagreement(self):
        self.assertEqual(self.app.selectbox[0].value, 1)
        self.say('3번 질문으로 이동해 줘')
        self.assertEqual(self.engine.state.current_question_index, 2)
        self.assertEqual(self.app.selectbox[0].value, 1)
        self.click('선택 문항으로 이동')
        self.assertEqual(self.engine.state.current_question_index, 0)

    def test_progress_unchanged(self):
        self.click('자주'); self.unchanged('지금 몇 번째 질문이야?')
        self.assertIn('응답 1개', self.reply())
        self.assertIn('미응답 10개', self.reply())

    def test_show_specific_and_current(self):
        self.click('자주'); self.say('3번 질문으로 이동해 줘')
        self.unchanged('1번 질문에 뭐라고 답했어?')
        self.assertIn('자주', self.reply())
        self.unchanged('현재 질문의 답변 보여줘')
        self.assertIn('아직 응답하지 않은', self.reply())

    def test_show_previous(self):
        self.click('드물게'); self.say('다음 질문으로 넘어가 줘')
        self.unchanged('이전 질문의 답변 보여줘')
        self.assertIn('드물게', self.reply())

    def test_show_skipped(self):
        self.say('이 질문은 건너뛸게'); self.unchanged('1번 질문에 뭐라고 답했어?')
        self.assertIn('건너뛴', self.reply())

    def test_last_answer_tracks_successful_edit(self):
        self.click('자주'); self.say('3번 질문으로 이동해 줘'); self.click('드물게')
        self.say('1번 질문으로 이동해 줘'); self.click('가끔')
        self.say('3번 질문으로 이동해 줘')
        self.unchanged('내가 앞에서 뭐라고 답했지?')
        self.assertIn('1번', self.reply()); self.assertIn('가끔', self.reply())
        self.say('방금 답변 수정할게')
        self.assertEqual(self.engine.state.current_question_index, 0)

    def test_unknown_last_answer(self):
        self.unchanged('방금 답변 수정할게')
        self.assertIn('번호', self.reply())

    def test_edit_does_not_change_answer(self):
        self.say('3번 질문으로 이동해 줘'); self.click('가끔')
        self.say('1번 질문으로 이동해 줘')
        answers = self.engine.state.answers
        self.say('3번 질문의 답변 수정할래')
        self.assertEqual(self.engine.state.current_question_index, 2)
        self.assertEqual(self.engine.state.answers, answers)
        self.click('자주'); self.assertEqual(self.engine.get_answer(3), 'OFTEN')

    def test_finish_only_review_and_block(self):
        self.say('설문을 끝내고 싶어')
        self.assertEqual(self.engine.state.survey_status, SurveyStatus.REVIEW)
        self.assertTrue(next(b for b in self.app.button if b.label == '설문 완료 확정').disabled)
        self.unchanged('설문을 끝내고 싶어')
        self.unchanged('3번 질문의 답변 수정할래')

    def test_unknown(self): self.unchanged('다음 주에 할게')
    def test_ambiguous(self): self.unchanged('2번')
    def test_rejected(self): self.unchanged('다음 질문으로 넘어가지 마')
    def test_compound(self): self.unchanged('이전 질문으로 가서 답을 바꿀게')
    def test_bad_number(self): self.unchanged('12번 질문으로 이동해 줘')

    def test_completed_guard_and_query(self):
        for _ in range(11): self.say('이 질문은 건너뛸게')
        self.say('설문을 끝내고 싶어')
        self.assertEqual(self.engine.state.survey_status, SurveyStatus.REVIEW)
        self.click('설문 완료 확정')
        self.unchanged('3번 질문의 답변 수정할래')
        self.unchanged('다음 질문으로 넘어가 줘')
        self.unchanged('현재 질문의 답변 보여줘')
        self.click('응답 수정하기'); self.click('자주')
        self.assertEqual(self.engine.get_answer(1), 'OFTEN')

    def test_rerun_no_replay(self):
        self.say('이 질문은 건너뛸게')
        before, messages = self.engine.state, list(self.app.session_state['messages'])
        self.app.run()
        self.assertEqual(self.engine.state, before)
        self.assertEqual(self.app.session_state['messages'], messages)

    def test_before_start_blocked(self):
        fresh = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
        self.assertTrue(fresh.chat_input[0].disabled)
        engine = fresh.session_state['survey_engine']
        before = engine.state
        with self.assertRaises(ValueError):
            route(engine, RuleBasedIntentParser().parse('다음'), None)
        self.assertEqual(engine.state, before)

    def test_parser_exception_is_hidden(self):
        before = self.engine.state
        with patch.object(RuleBasedIntentParser, 'parse', side_effect=RuntimeError('PRIVATE TRACE')):
            self.say('다음')
        self.assertEqual(self.engine.state, before)
        self.assertIn('오류', self.reply())
        self.assertNotIn('PRIVATE', self.reply())

    def test_current_edit_preserves_answer_and_first_previous_query(self):
        self.unchanged('이전 질문의 답변 보여줘')
        self.click('가끔')
        self.unchanged('현재 질문의 답변 수정할래')
        self.assertEqual(self.engine.get_answer(1), 'SOMETIMES')
