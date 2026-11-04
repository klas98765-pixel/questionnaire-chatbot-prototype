"""State transitions and rollback guarantees; no real questionnaire data."""

import unittest
from unittest.mock import patch

from questionnaire_chatbot.survey.engine import SurveyEngine, SurveyError
from questionnaire_chatbot.survey.models import QuestionStatus, SurveyState, SurveyStatus


class SurveyEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = SurveyEngine()
        self.engine.start()

    def assert_rejected(self, operation, error=SurveyError):
        before = self.engine.state
        with self.assertRaises(error):
            operation()
        self.assertEqual(self.engine.state, before)

    def complete_all(self):
        for _ in range(11):
            self.engine.save_answer("SOMETIMES")
            self.engine.next_question()
        self.engine.finish()

    def test_initial_and_start(self):
        fresh = SurveyEngine()
        self.assertEqual(fresh.state.survey_status, SurveyStatus.NOT_STARTED)
        self.assertTrue(fresh.state.session_id)
        self.assertEqual(fresh.progress().unanswered, 11)
        self.assertEqual(self.engine.state.current_question_index, 0)
        self.assertEqual(self.engine.state.survey_status, SurveyStatus.IN_PROGRESS)
        self.assert_rejected(self.engine.start)

    def test_save_answer(self):
        self.engine.save_answer("RARELY")
        self.assertEqual(self.engine.get_answer(1), "RARELY")
        self.assertEqual(self.engine.question_status(1), QuestionStatus.ANSWERED)

    def test_answer_does_not_advance(self):
        self.engine.save_answer("NEVER")
        self.assertEqual(self.engine.state.current_question_index, 0)

    def test_next(self):
        self.engine.save_answer("OFTEN")
        self.engine.next_question()
        self.assertEqual(self.engine.state.current_question_index, 1)

    def test_unanswered_next_blocked(self):
        self.assert_rejected(self.engine.next_question)

    def test_previous_from_unanswered(self):
        self.engine.goto_question(2)
        self.engine.previous_question()
        self.assertEqual(self.engine.state.current_question_index, 0)
        self.assert_rejected(self.engine.previous_question)

    def test_goto_from_unanswered(self):
        self.engine.goto_question(11)
        self.assertEqual(self.engine.state.current_question_index, 10)

    def test_invalid_goto(self):
        for value in (0, 12, -1, True, 1.0, "2", None):
            with self.subTest(value=value):
                self.assert_rejected(lambda: self.engine.goto_question(value))

    def test_skip(self):
        self.engine.skip_question()
        self.assertEqual(self.engine.question_status(1), QuestionStatus.SKIPPED)
        self.assertEqual(self.engine.state.current_question_index, 1)
        self.assertIsNone(self.engine.get_answer(1))

    def test_answer_skipped_question(self):
        self.engine.skip_question()
        self.engine.goto_question(1)
        self.engine.save_answer("UNSURE_OR_NA")
        self.assertEqual(self.engine.question_status(1), QuestionStatus.ANSWERED)
        self.assertNotIn(0, self.engine.state.skipped_questions)

    def test_edit_answer(self):
        self.engine.save_answer("NEVER")
        self.engine.next_question()
        self.engine.save_answer("RARELY")
        self.engine.previous_question()
        self.engine.save_answer("OFTEN")
        self.assertEqual(self.engine.get_answer(1), "OFTEN")
        self.assertEqual(self.engine.get_answer(2), "RARELY")

    def test_answer_preserved_on_skip(self):
        self.engine.save_answer("SOMETIMES")
        self.assert_rejected(self.engine.skip_question)
        self.assertEqual(self.engine.get_answer(1), "SOMETIMES")

    def test_unanswered_blocks_finish(self):
        self.engine.request_review()
        self.assert_rejected(self.engine.finish)

    def test_all_answered_completion(self):
        self.complete_all()
        self.assertEqual(self.engine.state.survey_status, SurveyStatus.COMPLETED)
        self.assertEqual(len(self.engine.summary()), 11)
        self.assertEqual(self.engine.progress().answered, 11)
        self.assertEqual(self.engine.progress().processed_fraction, 1)

    def test_completed_mutations_blocked(self):
        self.complete_all()
        for operation in (lambda: self.engine.save_answer("NEVER"),
                          self.engine.next_question, self.engine.previous_question,
                          lambda: self.engine.goto_question(2), self.engine.skip_question,
                          self.engine.request_review, self.engine.resume):
            self.assert_rejected(operation)

    def test_reopen(self):
        self.complete_all()
        old_answers = self.engine.state.answers
        self.engine.reopen_for_edit()
        self.assertEqual(self.engine.state.answers, old_answers)
        self.assertEqual(self.engine.state.current_question_index, 0)
        self.engine.save_answer("OFTEN")
        self.engine.request_review()
        self.engine.finish()
        self.assertEqual(self.engine.get_answer(1), "OFTEN")

    def test_invalid_answer_preserves_state(self):
        self.engine.save_answer("OFTEN")
        for value in ("invalid", "", 3, None, []):
            self.assert_rejected(lambda: self.engine.save_answer(value))

    def test_review_and_finish_separate(self):
        for _ in range(11):
            self.engine.skip_question()
        self.assertEqual(self.engine.state.survey_status, SurveyStatus.REVIEW)
        self.assertEqual(self.engine.progress().skipped, 11)
        self.engine.finish()
        self.assertEqual(self.engine.state.survey_status, SurveyStatus.COMPLETED)

    def test_finish_requires_review(self):
        self.assert_rejected(self.engine.finish)
        self.assert_rejected(self.engine.reopen_for_edit)

    def test_resume_review_targets_unanswered(self):
        self.engine.skip_question()
        self.engine.goto_question(8)
        self.engine.request_review()
        self.assert_rejected(lambda: self.engine.save_answer("OFTEN"))
        self.engine.resume()
        self.assertEqual(self.engine.state.current_question_index, 1)

    def test_progress_and_queries_do_not_mutate(self):
        self.engine.save_answer("NEVER")
        self.engine.next_question()
        self.engine.skip_question()
        before = self.engine.state
        progress = self.engine.progress()
        self.assertEqual((progress.answered, progress.skipped, progress.unanswered), (1, 1, 9))
        self.assertEqual(progress.processed_fraction, 2 / 11)
        self.assertEqual(self.engine.question_status(3), QuestionStatus.UNANSWERED)
        self.engine.summary()[0]["answer"] = "OFTEN"
        self.assertEqual(self.engine.state, before)
        self.assert_rejected(lambda: self.engine.get_answer(12))

    def test_snapshot_isolation(self):
        initial = SurveyState()
        engine = SurveyEngine(initial)
        initial.answers[0] = "OFTEN"
        self.assertEqual(engine.state.answers, {})
        snapshot = self.engine.save_answer("OFTEN")
        snapshot.answers.clear()
        self.assertEqual(self.engine.get_answer(1), "OFTEN")

    def test_unexpected_exception_rolls_back(self):
        with patch('questionnaire_chatbot.survey.engine.validate_state',
                   side_effect=RuntimeError("simulated validation failure")):
            self.assert_rejected(lambda: self.engine.save_answer("OFTEN"), RuntimeError)

    def test_invalid_initial_states(self):
        invalid_states = [
            SurveyState(current_question_index=11),
            SurveyState(answers={0: "OFTEN"}, skipped_questions={0},
                        survey_status=SurveyStatus.IN_PROGRESS),
            SurveyState(survey_status=SurveyStatus.COMPLETED),
            SurveyState(answers={0: "invalid"}, survey_status=SurveyStatus.IN_PROGRESS),
            SurveyState(answers={0: "OFTEN"}),
        ]
        for state in invalid_states:
            with self.assertRaises(SurveyError):
                SurveyEngine(state)

    def test_before_start_rejects_commands(self):
        self.engine = SurveyEngine()
        self.assert_rejected(lambda: self.engine.save_answer("OFTEN"))
        self.assert_rejected(lambda: self.engine.goto_question(2))
        self.assert_rejected(self.engine.request_review)


if __name__ == "__main__":
    unittest.main()
