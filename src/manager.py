import os
import shutil
from time import sleep
from tenacity import retry, stop_after_attempt, wait_exponential
from src.downloader import Downloader
from src.premiumize_api import PremiumizeAPI
from src.helper import on_fail, get_logger
from src.db import Database

logger = get_logger(__name__)


class Manager:
    def __init__(self, api_key: str, paths: tuple, dl_threads: int, dl_speed: int, chk_delay: int):
        self.blackhole_path, self.dl_path, self.done_path, self.config_path = paths
        self.to_download, self.to_premiumize, self.to_watch = [], [], {}
        self.chk_delay = chk_delay
        premiumize_cloud_root_dir_name = os.getenv("PREMIUMIZE_CLOUD_ROOT_DIR_NAME", "premiumarr")

        self.pm = PremiumizeAPI(api_key)
        self.dl = Downloader(self.dl_path, dl_threads, dl_speed)
        self.db = Database(self.config_path)

        self.test_basic_api_connection()

        self.premiumarr_root_id = self.pm.ensure_directory_exists(premiumize_cloud_root_dir_name)
        assert self.premiumarr_root_id, "Failed to get root folder ID"
        logger.info("Manager finished init")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry_error_callback=on_fail)
    def test_basic_api_connection(self):
        info = self.pm.get_account_info()
        logger.info(f"Premiumize account info: {info}")
        assert info["status"] == "success", f"Failed to get account info, check your API key! (ERR: {info})"

    @retry(stop=stop_after_attempt(1), wait=wait_exponential(min=1, max=10), retry_error_callback=on_fail)
    def restore_state(self):
        logger.info("Restoring state ...")

        # handle cases where the transaction was not completed
        # we can't ... we don't have the transaction id and the folder_id is not set when the transfer errored
        # or is not done yet.... ignoring for now

        to_premiumize = "SELECT full_path, category_path FROM data WHERE state = 'found'"
        for item in self.db.cursor.execute(to_premiumize).fetchall():
            self.to_premiumize.append((item[0], item[1]))

        to_watch = "SELECT dl_id, category_path, dl_retry_count FROM data WHERE state = 'uploaded'"
        for item in self.db.cursor.execute(to_watch).fetchall():
            dl_id, category_path, dl_retry_count = item
            self.to_watch[dl_id] = [dl_retry_count, category_path]

        to_download = "SELECT id, nzb_name, dl_folder_id, full_path FROM data WHERE state = 'in_premiumize_cloud'"
        for item in self.db.cursor.execute(to_download).fetchall():
            self.to_download.append(((item[0], item[1], item[2]), item[3]))

        logger.info("Restored state!")

    @retry(stop=stop_after_attempt(6), wait=wait_exponential(min=5, max=120), retry_error_callback=on_fail)
    def run(self):
        self.restore_state()

        while True:
            logger.info("Checking for incoming NZBs ...")
            self.check_folder_for_incoming_nzbs()

            logger.info("Uploading NZBs to premiumize downloader ...")
            self.upload_nzbs_to_premiumize_downloader()

            logger.info("Checking for finished cloud downloads ...")
            self.check_premiumize_downloader_state()

            logger.info("Checking if there are files to download to local ...")
            self.download_files_from_premiumize()

            logger.info("Cleaning up online files ...")
            self.cleanup_online_files()

            logger.info("Moving files to done folder ...")
            self.move_to_done()

            logger.info(f"Sleeping for {self.chk_delay}s ...\n")
            sleep(self.chk_delay)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(2, min=1, max=30), retry_error_callback=on_fail)
    def move_to_done(self):
        q = "SELECT id, nzb_name, category_path, full_path FROM data WHERE state = 'downloaded and online cleaned up'"
        items = self.db.cursor.execute(q).fetchall()
        for item in items:
            d_id, d_name, category, nzb_full_path = item
            category = category[1:] if category.startswith("/") else category  # normalize category path

            logger.info(f"Moving files to done folder for {d_name} ...")
            os.makedirs(f"{self.done_path}/{category}", exist_ok=True)
            shutil.move(f"{self.dl_path}/{d_name}", f"{self.done_path}/{category}/{d_name}")
            shutil.move(nzb_full_path, f"{self.config_path}/archive/{d_name}")  # move the nzb to archive

            self.db.cursor.execute("UPDATE data SET state = 'done' WHERE id = ?", (d_id,))
            self.db.conn.commit()
            logger.info(f"COMPLETED {d_name}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=5, max=45), retry_error_callback=on_fail)
    def cleanup_online_files(self):
        q = "SELECT id, dl_id, nzb_name FROM data WHERE state = 'downloaded'"
        for item in self.db.cursor.execute(q).fetchall():
            d_id, dl_id, d_name = item
            logger.info(f"Removing files from premiumize cloud for {d_name} ...")
            self.pm.delete_transfer(dl_id)
            self.db.cursor.execute("UPDATE data SET state = 'downloaded and online cleaned up' WHERE id = ?", (d_id,))
            self.db.conn.commit()

    # TODO: think about mutex and persistence
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(2, min=5, max=45), retry_error_callback=on_fail)
    def download_files_from_premiumize(self):
        while self.to_download:
            (d_id, d_name, d_folder_id), category = self.to_download[0]

            category = category[1:] if category.startswith("/") else category  # normalize category path
            links_and_paths: list[tuple[str, str]] = self.get_folder_as_download_links(d_folder_id, d_name)
            for link, path, name in links_and_paths:
                self.dl.dest = f"{self.dl_path}/{path}"
                logger.info(f'Downloading: "{self.dl_path}/{path}/{name}" from {link[:40]}...')
                self.dl.download(url=link, name=name)

            logger.info(f"Downloaded all files from {d_name} ...")
            logger.info(f"Removing the transfer from premiumize cloud and downloader for {d_name} ...")

            self.db.cursor.execute("UPDATE data SET state = 'downloaded' WHERE id = ?", (d_id,))
            self.db.conn.commit()
            self.to_download.pop(0)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(2, min=5, max=45), retry_error_callback=on_fail)
    def get_folder_as_download_links(self, f_id: str, path: str = "") -> list[tuple[str, str, str]]:
        ret = []
        folder = self.pm.list_folder(f_id)
        for item in folder.content:
            if item.is_folder():
                ret.extend(self.get_folder_as_download_links(item.id, f"{path}/{item.name}"))
            elif item.is_file():
                ret.append((item.link, f"{path}", item.name))

        return ret

    # IDEA: maybe I can to check_folder_for_incoming_nzbs and upload_nzbs_to_premiumize_downloader in a single thread
    # that way I would not need to use a mutex to prevent others from modifying the list
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), retry_error_callback=on_fail)
    def check_folder_for_incoming_nzbs(self):
        for root, _, files in os.walk(self.blackhole_path):
            for file in files:
                already_tracked = self.db.cursor.execute("SELECT * FROM data WHERE nzb_name = ?", (file,)).fetchone()

                if already_tracked:
                    continue
                if file.endswith(".nzb"):
                    category_path = root[len(self.blackhole_path) :]
                    logger.info(f'Found new NZB file: "{file}" in subfolder: "{category_path}"')

                    self.db.cursor.execute(
                        "INSERT INTO data (nzb_name, state, full_path, category_path) VALUES (?, ?, ?, ?)",
                        (file, "found", f"{root}/{file}", category_path),
                    )
                    self.db.conn.commit()

                    self.to_premiumize.append((f"{root}/{file}", category_path))
                else:
                    logger.info(f"Found non-NZB file: {file} - ignoring")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), retry_error_callback=on_fail)
    def upload_nzbs_to_premiumize_downloader(self):
        while self.to_premiumize:
            nzb_path, category_path = self.to_premiumize[0]
            logger.info(f"Uploading NZB file: {nzb_path} ...")

            q = "UPDATE data SET state = 'uploaded', dl_id = ? WHERE full_path = ?"
            dl_id = self.pm.upload_nzb(nzb_path, self.premiumarr_root_id)
            # Theoretically a crash here would cause the nzb to be uploaded again, but that is not really a issue
            self.db.cursor.execute(q, (dl_id, nzb_path))
            self.db.conn.commit()

            self.to_watch[dl_id] = [0, category_path]
            self.to_premiumize.pop(0)
            logger.info(f"Uploaded NZB file: {nzb_path}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), retry_error_callback=on_fail)
    def check_premiumize_downloader_state(self):
        if len(self.to_watch) == 0:  # nothing to watch, so don't bother the API
            return

        transfers = self.pm.get_transfers()
        # # single transfer item:
        # folder_id = None
        # id = 'abcAbcAbcAbc'
        # message = 'Loading...'
        # name = 'FileNameOfTheDL.nzb'
        # progress = 0
        # src = 'https://www.premiumize.me/api/job/src?id=abcAbcAbcAbc'
        # status = 'running'

        retry_cases = ["deleted", "banned", "error", "timeout"]

        # filter the transfers that are in the waiting list
        filtered_waiting = [item for item in transfers if item.id in self.to_watch]
        filtered_finished = [item for item in filtered_waiting if item.status == "finished"]
        filtered_failed = [item for item in filtered_waiting if item.status in retry_cases]

        for item in filtered_finished:
            from_watch = self.to_watch[item.id]

            q = "UPDATE data SET state = 'in premiumize cloud' AND dl_folder_id = ? WHERE dl_id = ?"
            self.db.cursor.execute(q, (item.folder_id, item.id))
            self.db.conn.commit()

            self.to_download.append(((item.id, item.name, item.folder_id), from_watch[1]))  # from_watch[1] == nzb_path
            logger.info(f"Added item to download list: {item}")

            self.to_watch.pop(item.id)
            logger.info(f"Removed item from watch list: {item}")

        for item in filtered_failed:
            self.to_watch[item.id][0] += 1  # increase retry_count
            q = "UPDATE data SET dl_retry_count = dl_retry_count + 1 WHERE dl_id = ?"
            self.db.cursor.execute(q, (item.id,))

            self.db.conn.commit()

            cur_retry_count = self.to_watch[item.id][0]
            max_retry_count = 6
            if cur_retry_count >= max_retry_count:
                # TODO: Do we really want to handle this here already?
                logger.error(f'premiumize failed for: "{item}", notifying sonarr (NOT IMPL. YET)...')  # TODO: IMPL.
                self.db.cursor.execute("UPDATE data SET state = 'failed' WHERE dl_id = ?", (item.id,))
                self.db.conn.commit()
                # TODO: Add a stage where nzbs for failed items are deleted and also from the cloud
                self.to_watch.pop(item.id)

            logger.warning(f"Item failed to download ({cur_retry_count}/{max_retry_count}): retrying ... {item}")
            self.pm.retry_transfer(item.id)  # unknown errors are resolvable by retrying on premiumize downloader

        # Print the status of the transfers that are still in progress
        progressing = [i for i in filtered_waiting if i.status != "finished" and i.status not in retry_cases]
        logger.info("Items in progress:")
        for item in progressing:
            logger.info(f"  {item.name}: {item.message}")
