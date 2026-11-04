"""Content contracts and compatibility with the existing survey engine."""

from dataclasses import FrozenInstanceError
import unittest

from questionnaire_chatbot.survey.models import CHOICE_CODES, QUESTION_COUNT, SurveyStatus
from questionnaire_chatbot.survey.engine import SurveyEngine
from questionnaire_chatbot.survey.questionnaire import CHOICES, get_question, get_questions


class QuestionnaireTests(unittest.TestCase):
    def test_exactly_eleven_questions(self):
        self.assertEqual(len(get_questions()), 11)
        self.assertEqual(len(get_questions()), QUESTION_COUNT)

    def test_ordered_one_based_numbers(self):
        self.assertEqual([q.question_number for q in get_questions()], list(range(1, 12)))

    def test_unique_numbers(self):
        numbers = [q.question_number for q in get_questions()]
        self.assertEqual(len(numbers), len(set(numbers)))

    def test_nonempty_text_and_timeframe(self):
        for question in get_questions():
            with self.subTest(number=question.question_number):
                self.assertIsInstance(question.question_text, str)
                self.assertTrue(question.question_text.strip())
                self.assertTrue(question.question_text.startswith("최근 7일 동안 "))

    def test_lookup_every_question(self):
        for question in get_questions():
            self.assertEqual(get_question(question.question_number), question)

    def test_invalid_number(self):
        for value in (0, 12, -1, True, False, 1.0, "1", None, []):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "문항 번호"):
                    get_question(value)

    def test_exactly_five_unique_choices(self):
        self.assertEqual(len(CHOICES), 5)
        self.assertEqual(len({choice.code for choice in CHOICES}), 5)

    def test_codes_match_engine(self):
        self.assertEqual({choice.code for choice in CHOICES}, CHOICE_CODES)

    def test_korean_labels_and_display_order(self):
        self.assertEqual([(choice.code, choice.label) for choice in CHOICES], [
            ("NEVER", "전혀 하지 않음"),
            ("RARELY", "드물게"),
            ("SOMETIMES", "가끔"),
            ("OFTEN", "자주"),
            ("UNSURE_OR_NA", "모르겠음·해당 없음"),
        ])

    def test_content_is_immutable(self):
        self.assertIsInstance(get_questions(), tuple)
        self.assertIsInstance(CHOICES, tuple)
        with self.assertRaises(FrozenInstanceError):
            get_question(1).question_text = "changed"
        with self.assertRaises(FrozenInstanceError):
            CHOICES[0].label = "changed"

    def test_content_lookup_does_not_change_state(self):
        engine = SurveyEngine()
        engine.start()
        engine.save_answer("OFTEN")
        before = engine.state
        get_questions()
        get_question(11)
        self.assertEqual(engine.state, before)

    def test_content_and_all_choices_work_with_engine(self):
        for choice in CHOICES:
            with self.subTest(code=choice.code):
                engine = SurveyEngine()
                engine.start()
                for question in get_questions():
                    self.assertEqual(engine.state.current_question_index, question.question_number - 1)
                    engine.save_answer(choice.code)
                    self.assertEqual(engine.get_answer(question.question_number), choice.code)
                    engine.next_question()
                self.assertEqual(engine.state.survey_status, SurveyStatus.REVIEW)
                engine.finish()
                self.assertEqual(engine.progress().answered, 11)


if __name__ == "__main__":
    unittest.main()
