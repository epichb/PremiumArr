import os
from time import sleep
from src.manager import Manager

BLACKHOLE_PATH = os.getenv("BLACKHOLE_PATH", "/blackhole")
DL_PATH = os.getenv("DOWNLOAD_PATH", "/downloads")
DONE_PATH = os.getenv("DONE_PATH", "/done")
DL_SPEED_LIMIT_KB = int(os.getenv("DOWNLOAD_SPEED_LIMIT_KB", "-1"))
DL_THREADS = int(os.getenv("DOWNLOAD_THREADS", "2"))
CHK_DELAY = int(os.getenv("RECHECK_PREMIUMIZE_CLOUD_DELAY", "60"))
API_KEY = os.getenv("API_KEY")


def check_path(path, name):
    if not os.path.exists(path):
        raise RuntimeError(f"{name} folder does not exist: {path}, check your mounts and configuration")
    if not os.access(path, os.W_OK):
        raise RuntimeError(f"{name} folder is not writable: {path}, check your mounts and configuration")


if __name__ == "__main__":
    if not API_KEY:
        raise RuntimeError("Please set the API_KEY environment variable")

    check_path(BLACKHOLE_PATH, "Blackhole")
    check_path(DL_PATH, "Download")
    check_path(DONE_PATH, "Done")
    paths = (BLACKHOLE_PATH, DL_PATH, DONE_PATH)
    while True:  # prevent the script from crashing
        try:
            manager = Manager(API_KEY, paths, DL_THREADS, DL_SPEED_LIMIT_KB, CHK_DELAY)
            manager.run()
        except Exception as e:  # pylint: disable=broad-except # we intentionally catch all exceptions
            print(f"Manager failed: {str(e)}")
            sleep(120)
