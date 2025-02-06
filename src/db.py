import sqlite3
import os
from src.helper import get_logger

logger = get_logger(__name__)


class Database:
    def __init__(self, config_path: str):
        # Create database file does not exist
        path = f"{config_path}/data.db"
        if not os.path.exists(path):
            logger.info(f"Database file does not exist, creating: {path}")
            open(path, "w", encoding="utf-8").close()

        self.conn = sqlite3.connect(path)
        self.cursor = self.conn.cursor()

        logger.info("Create tables if not exists...")

        # fmt: off
        self.cursor.execute("""
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
        """)  # fmt: on


# States:
# found: nzb file found in blackhole (will be uploaded to premiumize cloud)
# uploaded: nzb uploaded to premiumize cloud (waiting for the premiumize cloud to download it)
# in premiumize cloud: nzb is in premiumize cloud (will be downloaded to local)
# downloaded: nzb downloaded to local (will clean up the premiumize cloud next)
# downloaded and online cleaned up: premiumize cloud cleaned up (nzb file will be moved to done)
# done: nzb moved to done (nzb file will be deleted)
# failed: nzb failed to download (nzb file will be deleted / Cloud cleaned up and Sonar will be notified)
