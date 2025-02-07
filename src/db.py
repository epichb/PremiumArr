from datetime import datetime, timezone
import sqlite3
import os
from src.helper import get_logger

logger = get_logger(__name__)
time_fmt = "%Y-%m-%d %H:%M:%S.%f+00:00"


class Database:

    def __init__(self, config_path: str):
        self.path = f"{config_path}/data.db"
        if not os.path.exists(self.path):
            logger.info(f"Database file does not exist, creating: {self.path}")
            open(self.path, "w", encoding="utf-8").close()

        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.cursor = self.conn.cursor()  # for the main process
        safety_values = {
            1: "Single-Thread, all mutexes are disabled -> Unsafe for multithreading",
            2: "Multi-Thread, Connections must not be shared between threads",
            3: "Serialized, Full thread safety -> API calls are serialized across threads",
        }
        thread_safety = safety_values.get(sqlite3.threadsafety, "Unknown")
        logger.info(f"Connected to database with sqlite thread safety: {sqlite3.threadsafety}, means {thread_safety}")
        self.conn.row_factory = sqlite3.Row  # Enable named column access
        self._create_tables()

    def _create_tables(self):
        logger.info("Create tables if not exists...")
        cursor = self.conn.cursor()
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            state TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category_path TEXT NOT NULL,
            dl_id INTEGER,
            dl_retry_count INTEGER DEFAULT 0,
            dl_folder_id TEXT,
            nzb_name TEXT NOT NULL,
            cld_dl_timeout_time TIMESTAMP,
            cld_dl_move_retry_c INTEGER DEFAULT 0,
            state_retry_count INTEGER DEFAULT 0,
            full_path TEXT NOT NULL
        )
        """
        )
        cursor.close()

    def get_current_state(self):
        logger.debug("Fetching current state from database")
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, state, created_at, category_path, nzb_name, full_path "
            + "FROM data WHERE state NOT IN ('done', 'failed') ORDER BY id DESC"
        )
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]

    def get_done_failed_entries(self, limit=10, offset=0):
        logger.debug(f"Fetching done/failed entries from database with limit={limit} and offset={offset}")
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, state, created_at, category_path, nzb_name, full_path "
            + "FROM data WHERE state IN ('done', 'failed') ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in rows]

    def get_total_entries_count(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM data")
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def get_done_entries_count(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM data WHERE state = 'done'")
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def get_failed_entries_count(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM data WHERE state = 'failed'")
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def get_entries_count_by_state(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT state, COUNT(*) FROM data GROUP BY state")
        counts = {row["state"]: row["COUNT(*)"] for row in cursor.fetchall()}
        cursor.close()
        return counts

    def get_retry_counts(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT SUM(dl_retry_count) AS total_dl_retries, SUM(state_retry_count) AS total_state_retries FROM data"
        )
        row = cursor.fetchone()
        retry_counts = {"download": row["total_dl_retries"], "state": row["total_state_retries"]}
        cursor.close()
        return retry_counts

    def get_db_size_in_KB(self):
        raw_size = os.path.getsize(self.path)
        in_KB = raw_size / 1024
        return in_KB

    def get_last_added_timestamp(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT MAX(created_at) AS last_added FROM data")
        last_added = cursor.fetchone()["last_added"]
        time_fmt = "%Y-%m-%d %H:%M:%S"
        last_added = datetime.strptime(last_added, time_fmt).replace(tzinfo=timezone.utc) if last_added else None
        cursor.close()
        return last_added

    def get_last_done_timestamp(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT MAX(created_at) AS last_done FROM data WHERE state = 'done'")
        last_done = cursor.fetchone()["last_done"]
        last_done = datetime.strptime(last_done, time_fmt).replace(tzinfo=timezone.utc) if last_done else None
        cursor.close()
        return last_done
