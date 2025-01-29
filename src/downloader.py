import os
from pySmartDL import SmartDL


class Downloader:
    """The Downloader"""

    def __init__(self, dest: str, threads: int, speed_limit_kb: int = -1):
        self.dest = dest
        self.threads = threads
        self.speed_limit_kb = speed_limit_kb

    def download(self, url: str, name: str) -> None:
        if os.path.exists(f"{self.dest}/{name}"):
            print(f"File already downloaded -> skipping ({self.dest}{name})")
            return

        os.makedirs(self.dest, exist_ok=True)
        downloader = SmartDL(url, self.dest, threads=self.threads, progress_bar=True, timeout=60)

        if self.speed_limit_kb > 0:
            downloader.limit_speed(1024 * self.speed_limit_kb)  # 1024 bytes == 1 KB

        try:
            downloader.start()
            print(f"Download completed! File saved to: {downloader.get_dest()}")
        except Exception as e:  # pylint: disable=broad-except # we intentionally catch all exceptions
            print(f"Download failed: {str(e)}")
