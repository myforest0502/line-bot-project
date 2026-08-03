import logging
import os
from typing import Any

import psycopg


DATABASE_URL = os.getenv("DATABASE_URL")

logger = logging.getLogger(__name__)


def database_is_available() -> bool:
    """DATABASE_URLが設定されているか確認する。"""
    return bool(DATABASE_URL)


def get_db_connection():
    """Neon PostgreSQLへの接続を作る。"""
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URLが設定されていません。"
            "RenderのEnvironmentを確認してください。"
        )

    return psycopg.connect(DATABASE_URL)


def init_database() -> None:
    """ユーザー名とモードを保存するテーブルを作る。"""
    if not database_is_available():
        logger.warning(
            "DATABASE_URLがないため、ローカルの一時保存を使用します。"
        )
        return

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    name TEXT,
                    mode TEXT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

    logger.info("Neonデータベースの準備が完了しました。")


class PersistentUserStore:
    """
    今までの辞書と同じ書き方を保ちながら、
    名前またはモードをNeonへ保存するクラス。
    """

    ALLOWED_COLUMNS = {"name", "mode"}

    def __init__(self, column_name: str):
        if column_name not in self.ALLOWED_COLUMNS:
            raise ValueError(
                f"保存できない項目です: {column_name}"
            )

        self.column_name = column_name
        self._local_store: dict[str, Any] = {}

    def get(self, user_id: str, default: Any = None) -> Any:
        """保存されている値を取得する。"""
        if not database_is_available():
            return self._local_store.get(user_id, default)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {self.column_name}
                    FROM user_profiles
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()

        if row is None or row[0] is None:
            return default

        return row[0]

    def __contains__(self, user_id: str) -> bool:
        """「user_id in 保存箱」を使えるようにする。"""
        return self.get(user_id) is not None

    def __getitem__(self, user_id: str) -> Any:
        """「保存箱[user_id]」で値を取得する。"""
        value = self.get(user_id)

        if value is None:
            raise KeyError(user_id)

        return value

    def __setitem__(self, user_id: str, value: Any) -> None:
        """「保存箱[user_id] = 値」でNeonへ保存する。"""
        if not database_is_available():
            self._local_store[user_id] = value
            return

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO user_profiles (
                        user_id,
                        {self.column_name},
                        updated_at
                    )
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        {self.column_name}
                            = EXCLUDED.{self.column_name},
                        updated_at = NOW()
                    """,
                    (user_id, value),
                )

    def pop(self, user_id: str, default: Any = None) -> Any:
        """保存値を削除し、削除前の値を返す。"""
        old_value = self.get(user_id, default)

        if not database_is_available():
            return self._local_store.pop(user_id, default)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE user_profiles
                    SET
                        {self.column_name} = NULL,
                        updated_at = NOW()
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )

        return old_value


init_database()

user_names = PersistentUserStore("name")
user_modes = PersistentUserStore("mode")