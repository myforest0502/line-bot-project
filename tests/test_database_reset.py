"""ユーザープロフィール完全リセットのDB動作を検証する。"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from typing import Any


DATABASE_PATH = Path(__file__).resolve().parents[1] / "database.py"


def load_database_code(available, get_connection) -> dict:
    module = ast.parse(
        DATABASE_PATH.read_text(encoding="utf-8"),
        filename=str(DATABASE_PATH),
    )
    targets = {"PersistentUserStore", "reset_user_profile"}
    nodes = [
        node
        for node in module.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and node.name in targets
    ]
    namespace = {
        "Any": Any,
        "database_is_available": available,
        "get_db_connection": get_connection,
    }
    extracted = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(extracted)
    exec(compile(extracted, str(DATABASE_PATH), "exec"), namespace)
    store_class = namespace["PersistentUserStore"]
    namespace["user_names"] = store_class("name")
    namespace["user_modes"] = store_class("mode")
    return namespace


class FakeDatabase:
    def __init__(self, name: str, mode: str, fail_update: bool = False):
        self.profile = {"name": name, "mode": mode}
        self.fail_update = fail_update
        self.connection_count = 0
        self.update_count = 0

    def connect(self):
        self.connection_count += 1
        return FakeConnection(self)


class FakeConnection:
    def __init__(self, database: FakeDatabase):
        self.database = database

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return FakeCursor(self.database)


class FakeCursor:
    def __init__(self, database: FakeDatabase):
        self.database = database
        self.selected_row = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, params):
        normalized = " ".join(query.split())

        if normalized.startswith("SELECT name"):
            self.selected_row = (self.database.profile["name"],)
            return

        if normalized.startswith("SELECT mode"):
            self.selected_row = (self.database.profile["mode"],)
            return

        if normalized.startswith("UPDATE user_profiles"):
            self.database.update_count += 1
            if self.database.fail_update:
                raise RuntimeError("database update failed")
            self.database.profile["name"] = None
            self.database.profile["mode"] = None
            return

        raise AssertionError(f"Unexpected SQL: {normalized}")

    def fetchone(self):
        return self.selected_row


class DatabaseResetTest(unittest.TestCase):
    def test_local_reset_clears_name_and_mode(self) -> None:
        namespace = load_database_code(
            available=lambda: False,
            get_connection=lambda: None,
        )
        namespace["user_names"]["user-1"] = "利用者"
        namespace["user_modes"]["user-1"] = "study"

        namespace["reset_user_profile"]("user-1")

        self.assertIsNone(namespace["user_names"].get("user-1"))
        self.assertIsNone(namespace["user_modes"].get("user-1"))

    def test_neon_reset_clears_both_columns_in_one_update(self) -> None:
        database = FakeDatabase(name="利用者", mode="study")
        namespace = load_database_code(
            available=lambda: True,
            get_connection=database.connect,
        )

        namespace["reset_user_profile"]("user-1")

        self.assertEqual(1, database.connection_count)
        self.assertEqual(1, database.update_count)
        self.assertEqual({"name": None, "mode": None}, database.profile)
        # Render再起動後と同様にDBから再取得しても初期値になる。
        self.assertIsNone(namespace["user_names"].get("user-1"))
        self.assertIsNone(namespace["user_modes"].get("user-1"))

    def test_failed_neon_reset_does_not_leave_only_one_column_cleared(self) -> None:
        database = FakeDatabase(
            name="利用者",
            mode="study",
            fail_update=True,
        )
        namespace = load_database_code(
            available=lambda: True,
            get_connection=database.connect,
        )

        with self.assertRaisesRegex(RuntimeError, "database update failed"):
            namespace["reset_user_profile"]("user-1")

        self.assertEqual(1, database.update_count)
        self.assertEqual(
            {"name": "利用者", "mode": "study"},
            database.profile,
        )


if __name__ == "__main__":
    unittest.main()
