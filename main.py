import os
from time import sleep
from src.manager import Manager
from src.helper import get_logger

logger = get_logger(__name__)

BLACKHOLE_PATH = os.getenv("BLACKHOLE_PATH", "/blackhole")
DL_PATH = os.getenv("DOWNLOAD_PATH", "/downloads")
DONE_PATH = os.getenv("DONE_PATH", "/done")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/config")
DL_SPEED_LIMIT_KB = int(os.getenv("DOWNLOAD_SPEED_LIMIT_KB", "-1"))
DL_THREADS = int(os.getenv("DOWNLOAD_THREADS", "2"))
CHK_DELAY = int(os.getenv("RECHECK_PREMIUMIZE_CLOUD_DELAY", "60"))
API_KEY = os.getenv("API_KEY")


def check_path(dir_path, dir_name):
    logger.info(f"Checking {dir_name} directory: {dir_path}")
    if not os.path.exists(dir_path):
        raise RuntimeError(f"{dir_name} directory does not exist: {dir_path}, check your mounts and configuration")
    if not os.access(dir_path, os.W_OK):
        raise RuntimeError(f"{dir_name} directory is not writable: {dir_path}, check your mounts and configuration")


if __name__ == "__main__":
    if not API_KEY:
        raise RuntimeError("Please set the API_KEY environment variable")

    paths = {BLACKHOLE_PATH: "Blackhole", DL_PATH: "Download", DONE_PATH: "Done", CONFIG_PATH: "Config"}
    # sleep(120)
    for path, name in paths.items():
        check_path(path, name)

    # ensure the archive folder is in config path
    os.makedirs(f"{CONFIG_PATH}/archive", exist_ok=True)

    manager = Manager(API_KEY, list(paths.keys()), DL_THREADS, DL_SPEED_LIMIT_KB, CHK_DELAY)
    RESTART_AFTER_FATAL_TIME = 60
    while True:  # prevent the script from crashing
        try:
            manager.run()
        except Exception as e:  # pylint: disable=broad-except # we intentionally catch all exceptions
            logger.error(f"Manager failed: {str(e)} - restarting in {RESTART_AFTER_FATAL_TIME}s ...")
            sleep(RESTART_AFTER_FATAL_TIME)
