import os
from pySmartDL import SmartDL
from tenacity import retry, stop_after_attempt as tries, wait_exponential as w_exp
from src.helper import get_logger, RetryHandler

logger = get_logger(__name__)
rh = RetryHandler(logger)


class Downloader:
    """The Downloader"""

    def __init__(self, dest: str, threads: int, speed_limit_kb: int = -1):
        self.dest = dest
        self.threads = threads
        self.speed_limit_kb = speed_limit_kb

    @retry(stop=tries(3), wait=w_exp(2, min=30, max=90), retry_error_callback=rh.on_fail, before_sleep=rh.on_retry)
    def download(self, url: str, name: str) -> None:
        if os.path.exists(f"{self.dest}/{name}"):
            logger.info(f"File already downloaded -> skipping ({self.dest}{name})")
            return

        os.makedirs(self.dest, exist_ok=True)
        downloader = SmartDL(url, self.dest, threads=self.threads, progress_bar=True, timeout=60)

        if self.speed_limit_kb > 0:
            downloader.limit_speed(1024 * self.speed_limit_kb)  # 1024 bytes == 1 KB

        try:
            downloader.start()
            logger.info(f"Download completed! File saved to: {downloader.get_dest()}")
        except Exception as e:  # pylint: disable=broad-except # we intentionally catch all exceptions
            logger.error(f"Download failed: {str(e)}")
            raise RuntimeError(f"Download failed: {str(e)}")  # we want to retry the download if it fails
