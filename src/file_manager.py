import logging
import os
from pathlib import Path
import shutil
from tenacity import RetryError, retry, stop_after_attempt as tries, wait_exponential as w_exp
from src.db import Database
from src.helper import RetryHandler, get_logger, StateRetryError

logger = get_logger(__name__)
rh = RetryHandler(logger)

MAX_STATE_RETRY_COUNT = os.getenv("MAX_STATE_RETRY_COUNT", 3)


class FileManager:
    def __init__(self, db: Database):
        self.db = db

    def move_and_integrate(self, source, dest, id_for_retry=None):
        """Recursively moves/integrates source into dest, overwriting matching files.  If an id_for_retry is provided,
        the state_retry_count will be incremented and the state will be set to 'found'."""
        source, dest = map(Path, [source, dest])
        try:
            self._move_and_integrate(source, dest)
        except Exception as e:
            if not id_for_retry:
                logger.warning(f"Failed to move and integrate {source} into {dest}: {e}, ignoring for retry")
                raise RetryError(f"Failed to move and integrate {source} into {dest}: {e}")
                # we still raise the error so the caller can retry or handle it

            logger.error(f"Failed to move s(integrate) {source} into {dest}: {e}, degrading state of id:{id_for_retry}")
            q = "UPDATE data SET state_retry_count = state_retry_count + 1 WHERE id = ?"
            self.db.cursor.execute(q, (id_for_retry,))
            self.db.conn.commit()

            q = "SELECT nzb_name, state_retry_count FROM data WHERE id = ?"
            name, rt_count = self.db.cursor.execute(q, (id_for_retry,)).fetchone()
            if rt_count >= MAX_STATE_RETRY_COUNT:
                logger.error(f"State retry count exceeded for {name}, marking as failed")
                q = "UPDATE data SET state = 'failed' WHERE id = ?"
                self.db.cursor.execute(q, (id_for_retry,))
                self.db.conn.commit()
                raise StateRetryError(f"State retry count exceeded for {name}")

            logger.error(f"New state_retry_count is now {rt_count}/{MAX_STATE_RETRY_COUNT} - complete retrying...")
            q = (
                "UPDATE data SET state = 'found', cld_dl_move_retry_c = cld_dl_move_retry_c + 1, dl_id = NULL,"
                + " dl_retry_count = 0, dl_folder_id = NULL, cld_dl_timeout_time = NULL WHERE id = ?"
            )
            self.db.cursor.execute(q, (id_for_retry,))
            self.db.conn.commit()
            raise StateRetryError(f"Failed to move and integrate {source} into {dest}: {e}")

    @retry(stop=tries(2), wait=w_exp(2), retry_error_callback=rh.on_fail, before_sleep=rh.on_retry)
    def _move_and_integrate(self, source, dest):
        source, dest = map(Path, [source, dest])

        # check if source exists
        if not source.exists():
            raise FileNotFoundError(f"Source does not exist: {source}")

        if source.is_file():  # src is a file
            logging.debug(f"Moving file {source} to {dest}")
            if dest.exists():
                logging.warning(f"Overwriting file {dest}")
            shutil.move(str(source), str(dest))  # source is also clean
            return

        logging.debug(f"Creating directory {dest}")
        dest.mkdir(exist_ok=True)  # src is a directory (-> create dest directory)

        for item in source.iterdir():  # -> recursive call for each item in source
            self._move_and_integrate(item, dest / item.name)
        source.rmdir()  # rmdir only removes empty directories, so this is safe and only works when all worked
