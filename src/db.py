import sqlite3
import os
from src.helper import get_logger

logger = get_logger(__name__)


class Database:
    def __init__(self, config_path: str):
        path = f"{config_path}/data.db"
        if not os.path.exists(path):
            logger.info(f"Database file does not exist, creating: {path}")
            open(path, "w", encoding="utf-8").close()

        self.conn = sqlite3.connect(path, check_same_thread=False)
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


# States:
# found: nzb file found in blackhole (will be uploaded to premiumize cloud)
# uploaded: nzb uploaded to premiumize cloud (waiting for the premiumize cloud to download it)
# in premiumize cloud: nzb is in premiumize cloud (will be downloaded to local)
# downloaded: nzb downloaded to local (will clean up the premiumize cloud next)
# downloaded and online cleaned up: premiumize cloud cleaned up (nzb file will be moved to done)
# done: nzb moved to done (nzb file will be deleted)
# failed: nzb failed to download (nzb file will be deleted / Cloud cleaned up and Sonar will be notified)
