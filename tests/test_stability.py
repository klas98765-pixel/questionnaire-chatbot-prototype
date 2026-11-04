"""State invariants and complete UI scenarios for stabilization."""
from pathlib import Path
import random
import unittest

from streamlit.testing.v1 import AppTest
from questionnaire_chatbot.actions import Action, ActionKind, execute
from questionnaire_chatbot.intent.rule_based import RuleBasedIntentParser
from questionnaire_chatbot.intent.router import route
from questionnaire_chatbot.survey.engine import SurveyEngine, SurveyError, validate_state
from questionnaire_chatbot.survey.models import CHOICE_CODES, SurveyStatus

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


class StabilityTests(unittest.TestCase):
    def assert_invariants(self, engine):
        state, progress = engine.state, engine.progress()
        validate_state(state)
        answered, skipped = set(state.answers), state.skipped_questions
        unanswered = set(range(11)) - answered - skipped
        self.assertFalse(answered & skipped)
        self.assertEqual(len(answered) + len(skipped) + len(unanswered), 11)
        self.assertEqual(progress.total, 11)
        self.assertEqual(progress.unanswered, len(unanswered))
        self.assertTrue(set(state.answers.values()) <= CHOICE_CODES)
        self.assertTrue(0 <= state.current_question_index < 11)
        if state.survey_status == SurveyStatus.COMPLETED:
            self.assertFalse(unanswered)

    def test_seeded_state_transitions_and_failed_command_rollback(self):
        # Fixed seeds make failures reproducible. Include invalid operations in
        # every lifecycle phase, including completed and review states.
        kinds = list(ActionKind)
        for seed in range(10):
            rng = random.Random(seed)
            engine = SurveyEngine()
            for _ in range(300):
                kind = rng.choice(kinds)
                value = (rng.choice(sorted(CHOICE_CODES) + ['INVALID']) if kind == ActionKind.ANSWER
                         else rng.choice([0, 1, 3, 11, 12, True]) if kind == ActionKind.GOTO else None)
                before = engine.state
                try:
                    execute(engine, Action(kind, value))
                except SurveyError:
                    self.assertEqual(engine.state, before)
                self.assert_invariants(engine)

    def test_button_and_natural_language_transition_parity(self):
        cases = [
            ('다음 질문으로 넘어가 줘', Action(ActionKind.NEXT)),
            ('이전 질문 보여줘', Action(ActionKind.PREVIOUS)),
            ('이 질문은 건너뛸게', Action(ActionKind.SKIP)),
            ('3번 질문으로 이동해 줘', Action(ActionKind.GOTO, 3)),
            ('최종 검토 화면 보여줘', Action(ActionKind.REVIEW)),
            ('설문을 끝내고 싶어', Action(ActionKind.REVIEW)),
        ]
        for text, action in cases:
            for answered in [False, True]:
                with self.subTest(text=text, answered=answered):
                    left = SurveyEngine(); left.start()
                    if answered: left.save_answer('OFTEN')
                    right = SurveyEngine(left.state)
                    errors = []
                    for operation in [lambda: execute(left, action),
                                      lambda: execute(right, route(right, RuleBasedIntentParser().parse(text), 1 if answered else None).action)]:
                        try:
                            operation(); errors.append(False)
                        except SurveyError:
                            errors.append(True)
                    self.assertEqual(errors[0], errors[1])
                    self.assertEqual(left.state, right.state)
                    self.assert_invariants(left)

    def test_last_question_review_then_repeated_next_preserves_state(self):
        engine = SurveyEngine(); engine.start()
        for _ in range(11): engine.skip_question()
        self.assertEqual(engine.state.survey_status, SurveyStatus.REVIEW)
        before = engine.state
        with self.assertRaises(SurveyError): engine.next_question()
        self.assertEqual(engine.state, before)
        engine.finish()
        before = engine.state
        for kind in [ActionKind.ANSWER, ActionKind.GOTO, ActionKind.NEXT, ActionKind.SKIP]:
            with self.assertRaises(SurveyError):
                execute(engine, Action(kind, 'OFTEN' if kind == ActionKind.ANSWER else 1 if kind == ActionKind.GOTO else None))
            self.assertEqual(engine.state, before)

    def test_mixed_ui_scenario_and_invariants_at_each_step(self):
        app = AppTest.from_file(APP, default_timeout=15).run()
        def click(label):
            next(b for b in app.button if b.label == label).click().run()
            self.assertFalse(app.exception)
            self.assert_invariants(app.session_state['survey_engine'])
        def say(text):
            app.chat_input[0].set_value(text).run()
            self.assertFalse(app.exception)
            self.assert_invariants(app.session_state['survey_engine'])
        click('설문 시작하기'); click('가끔'); say('다음 질문으로 넘어가 줘')
        click('드물게'); say('3번 질문으로 이동해 줘'); click('건너뛰기')
        say('이전 질문 보여줘'); click('자주')
        self.assertEqual(app.session_state['survey_engine'].state.skipped_questions, set())
        say('방금 답변 수정할게'); click('전혀 하지 않음')
        say('2번 질문에 뭐라고 답했어?')
        self.assertIn('드물게', app.session_state['notice'][1])
        for n in range(4, 12):
            say(f'{n}번 질문으로 이동해 줘'); click('건너뛰기')
        engine = app.session_state['survey_engine']
        self.assertEqual((engine.progress().answered, engine.progress().skipped, engine.progress().unanswered), (3, 8, 0))
        self.assertEqual(engine.get_answer(1), 'SOMETIMES')
        self.assertEqual(engine.get_answer(2), 'RARELY')
        self.assertEqual(engine.get_answer(3), 'NEVER')
        click('설문 완료 확정')
        self.assertEqual(engine.state.survey_status, SurveyStatus.COMPLETED)
        before = engine.state
        say('3번 질문의 답변 수정할래')
        self.assertEqual(engine.state, before)

    def test_natural_language_event_replay_keeps_state_and_history(self):
        script = Path(APP).read_text()
        script += "\nif st.session_state.get('replay') is not None:\n    perform(None, None, st.session_state.replay, natural_text='이 질문은 건너뛸게')\n"
        app = AppTest.from_string(script, default_timeout=15).run()
        next(b for b in app.button if b.label == '설문 시작하기').click().run()
        version = app.session_state['ui_version']
        app.chat_input[0].set_value('이 질문은 건너뛸게').run()
        before = app.session_state['survey_engine'].state
        messages = list(app.session_state['messages'])
        app.session_state['replay'] = version
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['survey_engine'].state, before)
        self.assertEqual(app.session_state['messages'], messages)
