"""小テストの表示番号・入力番号・保存番号の対応を検証する。"""

from __future__ import annotations

import ast
import logging
import re
import unicodedata
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
        "calculate_quiz_result",
        "start_next_quiz",
        "handle_text_message",
    }
    function_nodes = []

    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name in target_names:
            node.decorator_list = []
            function_nodes.append(node)

    namespace = {
        "re": re,
        "unicodedata": unicodedata,
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
        "select_random_questions": lambda count: make_questions()[:count],
    }
    namespace["reset_user_profile"] = lambda user_id: (
        namespace["user_names"].pop(user_id, None),
        namespace["user_modes"].pop(user_id, None),
    )
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


def make_all_questions() -> list[dict]:
    return [
        {
            "id": 1000 + number,
            "question": f"テスト問題{number}",
            "choices": {key: f"選択肢{key}" for key in "ABCDE"},
            "answer": "ABCDE"[(number - 1) % 5],
            "explanation": f"テスト解説{number}",
        }
        for number in range(1, 31)
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
        app.user_names.clear()
        app.user_modes.clear()

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
                self.assertIn(f"{start_number + 1}:B2", message)
                self.assertIn(f"{start_number + 2}:C3", message)
                self.assertIn(f"{start_number + 3}:D1", message)
                self.assertIn(f"{start_number + 4}:E2", message)
                self.assertLess(
                    message.index("【回答方法】"),
                    message.index(f"【第{start_number}問】"),
                )
                self.assertEqual(1, message.count("【回答方法】"))

    def test_parser_accepts_common_input_variations_in_all_sets(self) -> None:
        answer_pairs = ["A1", "B2", "C3", "D1", "E2"]
        fullwidth_map = str.maketrans(
            "0123456789:ABCDE",
            "０１２３４５６７８９：ＡＢＣＤＥ",
        )

        for current_set in range(1, 7):
            start_number = ((current_set - 1) * 5) + 1
            expected_numbers = list(range(start_number, start_number + 5))
            explicit = [
                f"{number}:{answer}"
                for number, answer in zip(expected_numbers, answer_pairs)
            ]
            fullwidth = [value.translate(fullwidth_map) for value in explicit]
            valid_inputs = [
                "\n".join(explicit),
                " ".join(value.lower() for value in explicit),
                ",".join(explicit),
                "\t".join(explicit),
                "  ".join(value.replace(":", " : ") for value in explicit),
                "\n".join(value.replace("Ａ", " Ａ ").replace("１", " １ ")
                          for value in fullwidth),
                "\n".join(
                    f"{number} ： {answer[0]} {answer[1]}".translate(fullwidth_map)
                    for number, answer in zip(expected_numbers, answer_pairs)
                ),
                " ".join(value.replace(":", "") for value in explicit),
                "A1B2C3D1E2",
                "a1 b2 c3 d1 e2",
                "A 1   B 2  C 3  D 1  E 2",
            ]

            for user_message in valid_inputs:
                with self.subTest(
                    current_set=current_set,
                    user_message=user_message,
                ):
                    parsed = app.parse_quiz_answers(
                        user_message,
                        expected_numbers=expected_numbers,
                    )
                    self.assertEqual(expected_numbers, list(parsed))
                    self.assertEqual(
                        answer_pairs,
                        [
                            data["answer"] + data["confidence"]
                            for data in parsed.values()
                        ],
                    )

    def test_parser_rejects_invalid_or_incomplete_inputs(self) -> None:
        expected_numbers = list(range(6, 11))
        invalid_inputs = [
            "6:A4 7:B2 8:C3 9:D1 10:E2",
            "6:F1 7:B2 8:C3 9:D1 10:E2",
            "A1 B2 C3 D1",
            "A1 B2 C3 D1 E2 A1",
            "6:A1 6:B2 8:C3 9:D1 10:E2",
            "1:A1 2:B2 3:C3 4:D1 5:E2",
            "6:A1 7:B2 8:C3 9:D1",
            "6:A1 7:B2 8:C3 9:D1 10:E2 不明",
        ]

        for user_message in invalid_inputs:
            with self.subTest(user_message=user_message):
                self.assertEqual(
                    {},
                    app.parse_quiz_answers(
                        user_message,
                        expected_numbers=expected_numbers,
                    ),
                )

    def test_invalid_variations_do_not_modify_existing_answers(self) -> None:
        user_id = "invalid-input-test-user"
        original_answers = {
            number: {"answer": "A", "confidence": "1"}
            for number in range(1, 6)
        }
        invalid_inputs = [
            "6:A4 7:B2 8:C3 9:D1 10:E2",
            "6:F1 7:B2 8:C3 9:D1 10:E2",
            "A1 B2 C3 D1",
            "A1 B2 C3 D1 E2 A1",
            "6:A1 6:B2 8:C3 9:D1 10:E2",
            "1:A1 2:B2 3:C3 4:D1 5:E2",
        ]

        for user_message in invalid_inputs:
            with self.subTest(user_message=user_message):
                self.prepare_session(user_id, 2, {
                    number: dict(data)
                    for number, data in original_answers.items()
                })

                app.handle_text_message(make_text_event(user_id, user_message))

                session = app.study_sessions[user_id]
                self.assertEqual(original_answers, session["all_answers"])
                self.assertEqual("waiting_for_answers", session["status"])

    def test_global_numbers_are_saved_with_answer_and_confidence(self) -> None:
        user_id = "numbering-test-user"

        for current_set in range(1, 6):
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

    def test_final_set_completes_and_scores_all_thirty_questions(self) -> None:
        user_id = "completion-test-user"
        questions = make_all_questions()
        all_answers = {
            number: {
                "answer": questions[number - 1]["answer"],
                "confidence": str(((number - 1) % 3) + 1),
            }
            for number in range(1, 26)
        }
        final_answers = {
            26: {"answer": questions[25]["answer"], "confidence": "2"},
            27: {"answer": "E", "confidence": "3"},
            28: {"answer": questions[27]["answer"], "confidence": "1"},
            29: {"answer": "A", "confidence": "2"},
            30: {"answer": questions[29]["answer"], "confidence": "3"},
        }
        # 第27問の正答はB、第29問の正答はDなので、この2問だけ不正解。
        self.prepare_session(user_id, 6, all_answers)
        session = app.study_sessions[user_id]
        session["questions"] = questions[25:]
        session["all_questions"] = questions
        reply_messages = []
        continue_choice_calls = []
        function_globals = app.handle_text_message.__globals__
        original_reply = function_globals["reply_to_line"]
        original_continue = function_globals["reply_study_continue_choice"]
        function_globals["reply_to_line"] = (
            lambda _token, message: reply_messages.append(message)
        )
        function_globals["reply_study_continue_choice"] = (
            lambda token: continue_choice_calls.append(token)
        )
        answer_text = "\n".join(
            f"{number}:{data['answer']}{data['confidence']}"
            for number, data in final_answers.items()
        )

        try:
            app.handle_text_message(make_text_event(user_id, answer_text))
        finally:
            function_globals["reply_to_line"] = original_reply
            function_globals["reply_study_continue_choice"] = original_continue

        result = session["quiz_result"]
        self.assertEqual("quiz_completed", session["status"])
        self.assertEqual([], continue_choice_calls)
        self.assertEqual(30, result["total"])
        self.assertEqual(28, result["score"])
        self.assertEqual(30, len(result["details"]))
        self.assertEqual(list(range(1, 31)), [
            detail["question_number"] for detail in result["details"]
        ])
        self.assertEqual(
            [question["id"] for question in questions],
            [detail["question_id"] for detail in result["details"]],
        )
        self.assertEqual(
            [session["all_answers"][number]["confidence"] for number in range(1, 31)],
            [detail["confidence"] for detail in result["details"]],
        )
        self.assertIn("【結果】28 / 30問正解", reply_messages[0])

        app.handle_text_message(make_text_event(user_id, "続ける"))
        self.assertEqual("quiz_completed", session["status"])
        self.assertNotEqual("preparing_next", session["status"])

        with self.assertRaisesRegex(ValueError, "30問すべて出題済み"):
            app.start_next_quiz(user_id)

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

    def test_restart_command_completely_resets_every_session_state(self) -> None:
        user_id = "reset-test-user"
        reset_cases = [
            ("waiting_for_answers", "study"),
            ("waiting_for_continue", "study"),
            ("preparing_next", "study"),
            ("quiz_completed", "study"),
            (None, "study"),
            (None, "chat"),
            (None, "explain"),
            (None, "normal"),
        ]
        function_globals = app.handle_text_message.__globals__
        original_reply = function_globals["reply_to_line"]
        original_create_text_response = function_globals["create_text_response"]
        original_continue = function_globals["reply_study_continue_choice"]

        try:
            for status, mode in reset_cases:
                with self.subTest(status=status, mode=mode):
                    app.user_states[user_id] = "waiting_name"
                    app.user_names[user_id] = "テストユーザー"
                    app.user_modes[user_id] = mode

                    if status is None:
                        app.study_sessions.pop(user_id, None)
                    else:
                        app.study_sessions[user_id] = {
                            "status": status,
                            "current_set": 6,
                            "total_sets": 6,
                            "questions": make_questions(),
                            "all_questions": make_all_questions(),
                            "all_answers": {
                                1: {"answer": "A", "confidence": "1"}
                            },
                            "quiz_result": {"score": 1, "total": 30},
                        }

                    reply_messages = []
                    function_globals["reply_to_line"] = (
                        lambda _token, message: reply_messages.append(message)
                    )
                    function_globals["create_text_response"] = (
                        lambda *args, **kwargs: self.fail(
                            "リセット命令が通常のAI会話へ流れました。"
                        )
                    )
                    function_globals["reply_study_continue_choice"] = (
                        lambda *args, **kwargs: self.fail(
                            "リセット後に以前の学習状態が処理されました。"
                        )
                    )

                    app.handle_text_message(
                        make_text_event(user_id, "ふりだしにもどる")
                    )

                    self.assertNotIn(user_id, app.user_states)
                    self.assertNotIn(user_id, app.study_sessions)
                    self.assertNotIn(user_id, app.user_modes)
                    self.assertNotIn(user_id, app.user_names)
                    self.assertEqual(1, len(reply_messages))
                    self.assertIn("ふりだしに戻した", reply_messages[0])
        finally:
            function_globals["reply_to_line"] = original_reply
            function_globals["create_text_response"] = original_create_text_response
            function_globals["reply_study_continue_choice"] = original_continue

    def test_restart_command_reports_database_failure_without_ai_fallback(self) -> None:
        user_id = "reset-failure-test-user"
        app.user_states[user_id] = "waiting_name"
        app.user_names[user_id] = "テストユーザー"
        app.user_modes[user_id] = "study"
        app.study_sessions[user_id] = {
            "status": "waiting_for_continue",
            "current_set": 2,
        }
        reply_messages = []
        function_globals = app.handle_text_message.__globals__
        original_reply = function_globals["reply_to_line"]
        original_reset = function_globals["reset_user_profile"]
        original_create_text_response = function_globals["create_text_response"]
        function_globals["reply_to_line"] = (
            lambda _token, message: reply_messages.append(message)
        )
        function_globals["reset_user_profile"] = (
            lambda _user_id: (_ for _ in ()).throw(RuntimeError("DB unavailable"))
        )
        function_globals["create_text_response"] = (
            lambda *args, **kwargs: self.fail(
                "DB障害時に通常のAI会話へ流れました。"
            )
        )

        try:
            app.handle_text_message(
                make_text_event(user_id, "ふりだしにもどる")
            )
        finally:
            function_globals["reply_to_line"] = original_reply
            function_globals["reset_user_profile"] = original_reset
            function_globals["create_text_response"] = original_create_text_response

        self.assertNotIn(user_id, app.user_states)
        self.assertNotIn(user_id, app.study_sessions)
        self.assertEqual("テストユーザー", app.user_names[user_id])
        self.assertEqual("study", app.user_modes[user_id])
        self.assertEqual(1, len(reply_messages))
        self.assertNotIn("全部ふりだしに戻した", reply_messages[0])
        self.assertIn("最後まで確認できなかった", reply_messages[0])


if __name__ == "__main__":
    unittest.main()
