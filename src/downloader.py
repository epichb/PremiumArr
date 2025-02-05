import os
from pySmartDL import SmartDL
from tenacity import retry, stop_after_attempt as tries, wait_exponential as w_exp
from src.db import Database
from src.helper import get_logger, RetryHandler

logger = get_logger(__name__)
rh = RetryHandler(logger)


class Downloader:
    """The Downloader"""

    def __init__(self, dest: str, threads: int, db: Database, speed_limit_kb: int = -1):
        self.dest = dest
        self.threads = threads
        self.speed_limit_kb = speed_limit_kb
        self.db = db

    def on_fail(self, retry_state):
        logger.error(f"TESTMSG: Download failed after {retry_state.attempt_number} attempts")
        rh.on_fail(retry_state)

    # TODO: this needs to raise an exception, or somehow mark the dl self as failed in the db - reraise not working?
    @retry(
        stop=tries(3), wait=w_exp(min=2, max=10), retry_error_callback=on_fail, before_sleep=rh.on_retry, reraise=True
    )
    def download(self, url: str, name: str) -> None:
        if os.path.exists(f"{self.dest}/{name}"):
            logger.info(f"File already downloaded -> skipping ({self.dest}{name})")
            return

        os.makedirs(self.dest, exist_ok=True)
        downloader = SmartDL(url, self.dest, threads=self.threads, progress_bar=True, timeout=60)

        if self.speed_limit_kb > 0:
            downloader.limit_speed(1024 * self.speed_limit_kb)  # 1024 bytes == 1 KB

        downloader.start()
        logger.info(f"Download completed! File saved to: {downloader.get_dest()}")
        # raise RuntimeError("Download failed") # for testing purposes
