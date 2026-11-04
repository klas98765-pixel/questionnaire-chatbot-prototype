"""Explicit Korean inputs and expected intents, including unsafe counterexamples."""

import unittest
from unittest.mock import patch

from questionnaire_chatbot.intent.base import IntentClassifier
from questionnaire_chatbot.intent.rule_based import RuleBasedIntentParser
from questionnaire_chatbot.intent.schemas import Intent, ParseStatus, TargetReference
from questionnaire_chatbot.survey.engine import SurveyEngine
from questionnaire_chatbot.actions import ActionKind


CASES = {
    'NEXT': ['다음 질문으로 넘어가 줘', '다음 문항 보여줘', '다음으로 가자'],
    'PREVIOUS': ['이전 질문 보여줘', '아까 질문 다시 보여줘', '전 질문으로 돌아가 줘'],
    'SKIP': ['이 질문은 건너뛸게', '모르겠으니까 넘어갈래', '이번 문항은 패스할게'],
    'EDIT': ['방금 답변 수정할게', '이전에 선택한 답을 바꾸고 싶어', '3번 질문의 답변 수정할래'],
    'GOTO': ['3번 질문으로 이동해 줘', '5번 문항 보여줘', '11번 질문으로 돌아갈래'],
    'PROGRESS': ['지금 몇 번째 질문이야?', '설문 얼마나 진행했어?', '몇 개 남았어?'],
    'SHOW_ANSWER': ['내가 앞에서 뭐라고 답했지?', '2번 질문에 뭐라고 답했어?', '현재 질문의 답변 보여줘'],
    'REVIEW': ['답변 전체를 검토하고 싶어', '최종 검토 화면 보여줘'],
    'FINISH': ['설문을 끝내고 싶어', '이제 설문 마칠게'],
}


class RuleBasedIntentTests(unittest.TestCase):
    def setUp(self):
        self.parser = RuleBasedIntentParser()

    def check_examples(self, intent):
        for text in CASES[intent]:
            with self.subTest(text=text, expected=intent):
                result = self.parser.parse(text)
                self.assertEqual(result.intent.value, intent)
                self.assertEqual(result.status, ParseStatus.MATCHED)

    def test_next(self): self.check_examples('NEXT')
    def test_previous(self): self.check_examples('PREVIOUS')
    def test_skip(self): self.check_examples('SKIP')
    def test_edit(self): self.check_examples('EDIT')
    def test_goto(self): self.check_examples('GOTO')
    def test_progress(self): self.check_examples('PROGRESS')
    def test_show_answer(self): self.check_examples('SHOW_ANSWER')
    def test_review(self): self.check_examples('REVIEW')
    def test_finish(self): self.check_examples('FINISH')

    def test_unknown_general_answers(self):
        for text in ['', '   ', '다음 주에 할게', '다음 날에는 음악을 들었어',
                     '가끔', '오늘 날씨 알려줘', '다음 질문으로 넘어가 줘 라고 말했어']:
            with self.subTest(text=text):
                self.assertEqual(self.parser.parse(text).status, ParseStatus.UNKNOWN)

    def test_ambiguous_bare_numbers(self):
        for text in ['2번', '2 번!', '3번으로', '12번']:
            self.assertEqual(self.parser.parse(text).intent, Intent.AMBIGUOUS)

    def test_ambiguous_multiple_commands(self):
        for text in ['다음 그리고 이전', '이전 질문으로 가서 답을 바꿀게', '다음 질문 보여줘 그리고 건너뛸게',
                     '3번 질문으로 이동하고 답변 수정할래', '다음 질문 보여줘. 이전 질문 보여줘']:
            with self.subTest(text=text):
                result = self.parser.parse(text)
                self.assertEqual(result.intent, Intent.AMBIGUOUS)
                self.assertIsNone(result.target_question)

    def test_rejected_negatives(self):
        for text in ['다음 질문으로 넘어가지 마', '다음 질문으로 넘어가지 마세요',
                     '이전 질문으로 가지 마', '답변 수정하지 마', '설문 끝내지 마',
                     '다음으로 가지 말고 이전 질문 보여줘', '설문 안할래']:
            with self.subTest(text=text):
                self.assertEqual(self.parser.parse(text).intent, Intent.REJECTED)

    def test_invalid_target_numbers(self):
        for number in [0, 12, -1, 999]:
            for text in [f'{number}번 질문으로 이동해 줘', f'{number}번 질문의 답변 수정할래',
                         f'{number}번 질문에 뭐라고 답했어?']:
                with self.subTest(text=text):
                    result = self.parser.parse(text)
                    self.assertEqual(result.status, ParseStatus.REJECTED)
                    self.assertNotEqual(result.intent, Intent.GOTO)

    def test_number_extraction(self):
        for number in range(1, 12):
            result = self.parser.parse(f'{number}번 질문으로 이동해 줘')
            self.assertEqual(result.target_question, number)
            self.assertIsNone(result.target_reference)
        self.assertEqual(self.parser.parse('3번 질문의 답변 수정할래').target_question, 3)
        self.assertEqual(self.parser.parse('2번 질문에 뭐라고 답했어?').target_question, 2)

    def test_relative_references(self):
        expected = {'현재 질문의 답변 보여줘': TargetReference.CURRENT,
                    '이전 질문의 답변 보여줘': TargetReference.PREVIOUS,
                    '방금 답변 수정할게': TargetReference.LAST_ANSWER,
                    '내가 앞에서 뭐라고 답했지?': TargetReference.LAST_ANSWER}
        for text, reference in expected.items():
            result = self.parser.parse(text)
            self.assertEqual(result.target_reference, reference)
            self.assertIsNone(result.target_question)

    def test_spacing_punctuation_politeness(self):
        for text in ['  다음   질문으로 넘어가 주세요! ', '다음\n문항\t보여주세요。',
                     '다음질문으로넘어가줘?!']:
            result = self.parser.parse(text)
            self.assertEqual(result.intent, Intent.NEXT)
            self.assertEqual(result.original_text, text)
        self.assertEqual(self.parser.classify('３번 문항 보여주세요！'), 'GOTO')

    def test_protocol_contract(self):
        classifier: IntentClassifier = self.parser
        for intent, texts in CASES.items():
            self.assertIs(type(classifier.classify(texts[0])), str)
            self.assertEqual(classifier.classify(texts[0]), intent)

    def test_state_never_changed_or_engine_called(self):
        engine = SurveyEngine()
        engine.start()
        engine.save_answer('OFTEN')
        before = engine.state
        with patch.object(SurveyEngine, '_apply', side_effect=AssertionError('Parser called engine')):
            for texts in CASES.values():
                for text in texts:
                    self.parser.parse(text)
            self.parser.parse('2번')
            self.parser.parse('다음 질문으로 넘어가지 마')
        self.assertEqual(engine.state, before)

    def test_direct_action_names_compatible(self):
        for name in ['NEXT', 'PREVIOUS', 'SKIP', 'GOTO', 'REVIEW']:
            self.assertEqual(ActionKind(name).value, Intent[name].value)
        # No conversion of a FINISH request into an executable finish action here.
        self.assertEqual(self.parser.parse('설문을 끝내고 싶어').intent, Intent.FINISH)

    def test_nonstring_input(self):
        for value in [None, 2, [], {}]:
            with self.assertRaises(TypeError):
                self.parser.parse(value)

    def test_large_number_rejected(self):
        self.assertEqual(self.parser.parse('9' * 5000 + '번 질문으로 이동해 줘').intent, Intent.REJECTED)


if __name__ == '__main__':
    unittest.main()
