"""小テストの表示番号・入力番号・保存番号の対応を検証する。"""

from __future__ import annotations

import ast
import logging
import re
import unittest
from pathlib import Path
from types import SimpleNamespace


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def load_current_app_functions() -> SimpleNamespace:
    """外部SDKをimportせず、app.pyの対象関数本体をそのまま読み込む。"""
    module = ast.parse(
        APP_PATH.read_text(encoding="utf-8"),
        filename=str(APP_PATH),
    )
    target_names = {
        "format_quiz_messages",
        "parse_quiz_answers",
        "handle_text_message",
    }
    function_nodes = []

    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name in target_names:
            node.decorator_list = []
            function_nodes.append(node)

    namespace = {
        "re": re,
        "logging": logging,
        "threading": SimpleNamespace(Thread=None),
        "study_sessions": {},
        "user_states": {},
        "user_names": {},
        "user_modes": {},
        "reply_to_line": lambda *args, **kwargs: None,
        "reply_mode_select": lambda *args, **kwargs: None,
        "reply_study_continue_choice": lambda *args, **kwargs: None,
        "reply_study_ready_choice": lambda *args, **kwargs: None,
        "create_text_response": lambda *args, **kwargs: "unused",
        "prepare_and_send_quiz": lambda *args, **kwargs: None,
        "prepare_and_send_next_quiz": lambda *args, **kwargs: None,
    }
    extracted_module = ast.Module(body=function_nodes, type_ignores=[])
    ast.fix_missing_locations(extracted_module)
    exec(compile(extracted_module, str(APP_PATH), "exec"), namespace)
    return SimpleNamespace(**namespace)


app = load_current_app_functions()


def make_questions() -> list[dict]:
    return [
        {
            "id": number,
            "question": f"テスト問題{number}",
            "choices": {key: f"選択肢{key}" for key in "ABCDE"},
            "answer": "A",
            "explanation": "テスト解説",
        }
        for number in range(1, 6)
    ]


def make_text_event(user_id: str, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        message=SimpleNamespace(text=text),
        source=SimpleNamespace(user_id=user_id),
        reply_token="test-reply-token",
    )


class QuizAnswerNumberingTest(unittest.TestCase):
    def setUp(self) -> None:
        app.study_sessions.clear()
        app.user_states.clear()

    def prepare_session(
        self,
        user_id: str,
        current_set: int,
        all_answers: dict | None = None,
    ) -> None:
        app.user_names[user_id] = "テストユーザー"
        app.user_modes[user_id] = "study"
        app.study_sessions[user_id] = {
            "status": "waiting_for_answers",
            "current_set": current_set,
            "total_sets": 6,
            "questions": make_questions(),
            "all_questions": make_questions(),
            "all_answers": all_answers or {},
        }

    def test_displayed_numbers_and_examples_match_each_set(self) -> None:
        questions = make_questions()

        for current_set in range(1, 7):
            with self.subTest(current_set=current_set):
                start_number = ((current_set - 1) * 5) + 1
                message = app.format_quiz_messages(
                    questions,
                    start_number=start_number,
                )[0]

                for number in range(start_number, start_number + 5):
                    self.assertIn(f"【第{number}問】", message)
                self.assertIn(f"{start_number}:A1", message)
                self.assertIn(f"{start_number + 1}:C3", message)
                self.assertIn(f"{start_number + 2}:E2", message)

    def test_global_numbers_are_saved_with_answer_and_confidence(self) -> None:
        user_id = "numbering-test-user"

        for current_set in range(1, 7):
            with self.subTest(current_set=current_set):
                start_number = ((current_set - 1) * 5) + 1
                expected_numbers = list(range(start_number, start_number + 5))
                answer_text = "\n".join(
                    f"{number}:A1" for number in expected_numbers
                )
                self.prepare_session(user_id, current_set)

                app.handle_text_message(make_text_event(user_id, answer_text))

                session = app.study_sessions[user_id]
                self.assertEqual(expected_numbers, sorted(session["all_answers"]))
                self.assertTrue(
                    all(
                        answer == {"answer": "A", "confidence": "1"}
                        for answer in session["all_answers"].values()
                    )
                )
                self.assertEqual("waiting_for_continue", session["status"])

    def test_each_set_rejects_numbers_outside_its_range(self) -> None:
        user_id = "range-validation-test-user"

        for current_set in range(1, 7):
            with self.subTest(current_set=current_set):
                invalid_start = 6 if current_set == 1 else 1
                invalid_text = "\n".join(
                    f"{number}:A1"
                    for number in range(invalid_start, invalid_start + 5)
                )
                self.prepare_session(user_id, current_set)

                app.handle_text_message(make_text_event(user_id, invalid_text))

                session = app.study_sessions[user_id]
                self.assertEqual({}, session["all_answers"])
                self.assertEqual("waiting_for_answers", session["status"])

    def test_second_set_does_not_overwrite_first_set_answers(self) -> None:
        user_id = "overwrite-test-user"
        original_answers = {
            number: {"answer": "B", "confidence": "2"}
            for number in range(1, 6)
        }
        self.prepare_session(user_id, 2, original_answers.copy())
        reply_messages = []
        function_globals = app.handle_text_message.__globals__
        original_reply = function_globals["reply_to_line"]
        function_globals["reply_to_line"] = (
            lambda _token, message: reply_messages.append(message)
        )

        try:
            app.handle_text_message(
                make_text_event(
                    user_id,
                    "1:A1\n2:B2\n3:C3\n4:D2\n5:E1",
                )
            )
        finally:
            function_globals["reply_to_line"] = original_reply

        session = app.study_sessions[user_id]
        self.assertEqual(original_answers, session["all_answers"])
        self.assertEqual("waiting_for_answers", session["status"])
        self.assertIn("第6問から第10問まで", reply_messages[0])
        self.assertIn("6:A1", reply_messages[0])
        self.assertIn("10:E1", reply_messages[0])


if __name__ == "__main__":
    unittest.main()
