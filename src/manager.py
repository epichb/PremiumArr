import os
import shutil
from time import sleep
from datetime import timedelta
from tenacity import RetryError, retry, stop_after_attempt as tries, wait_exponential as w_exp
from src.downloader import Downloader
from src.premiumize_api import PremiumizeAPI
from src.helper import UTCDateTime, RetryHandler, StateRetryError, get_logger
from src.file_manager import FileManager
from src.db import Database

logger = get_logger(__name__)
rh = RetryHandler(logger)
MAX_RETRY_COUNT = os.getenv("MAX_RETRY_COUNT", 6)
MAX_CLOUD_DL_MOVE_RETRY_COUNT = os.getenv("MAX_CLOUD_DL_MOVE_RETRY_COUNT", 3)


class Manager:
    def __init__(self, api_key: str, paths: tuple, dl_threads: int, dl_speed: int, chk_delay: int):
        self.blackhole_path, self.dl_path, self.done_path, self.config_path = paths
        self.to_download, self.to_premiumize, self.to_watch = [], [], {}
        self.chk_delay = chk_delay
        premiumize_cloud_root_dir_name = os.getenv("PREMIUMIZE_CLOUD_ROOT_DIR_NAME", "premiumarr")

        self.pm = PremiumizeAPI(api_key)
        self.dl = Downloader(self.dl_path, dl_threads, dl_speed)
        self.db = Database(self.config_path)
        self.fm = FileManager(self.db)

        self.test_basic_api_connection()

        self.premiumarr_root_id = self.pm.ensure_directory_exists(premiumize_cloud_root_dir_name)
        assert self.premiumarr_root_id, "Failed to get root folder ID"
        logger.info("Manager finished init")

    @retry(stop=tries(3), wait=w_exp(max=10), retry_error_callback=rh.on_fail, before_sleep=rh.on_retry)
    def test_basic_api_connection(self):
        info = self.pm.get_account_info()
        logger.info(f"Premiumize account info: {info}")
        assert info["status"] == "success", f"Failed to get account info, check your API key! (ERR: {info})"

    @retry(stop=tries(1), wait=w_exp(max=10), retry_error_callback=rh.on_fail, before_sleep=rh.on_retry)
    def restore_state(self):
        logger.info("Restoring state ...")

        # handle cases where the transaction was not completed
        # we can't ... we don't have the transaction id and the folder_id is not set when the transfer errored
        # or is not done yet.... ignoring for now

        q = "SELECT full_path, category_path FROM data WHERE state = 'found'"
        for item in self.db.cursor.execute(q).fetchall():
            self.to_premiumize.append((item[0], item[1]))

        to_watch = "SELECT dl_id, category_path, dl_retry_count FROM data WHERE state = 'uploaded'"
        for item in self.db.cursor.execute(to_watch).fetchall():
            dl_id, category_path, dl_retry_count = item
            self.to_watch[dl_id] = [dl_retry_count, category_path]

        to_download = "SELECT id, nzb_name, dl_folder_id, category_path FROM data WHERE state = 'in premiumize cloud'"
        for item in self.db.cursor.execute(to_download).fetchall():
            self.to_download.append(((item[0], item[1], item[2]), item[3]))

        logger.info("Restored state!")

    @retry(stop=tries(6), wait=w_exp(min=5, max=120), retry_error_callback=rh.on_fail, before_sleep=rh.on_retry)
    def run(self):
        self.restore_state()
        logger.info(f"Starting manager loop ... with check delays of {self.chk_delay}s")

        while True:
            logger.debug("Checking for incoming NZBs ...")
            self.check_folder_for_incoming_nzbs()

            logger.debug("Uploading NZBs to premiumize downloader ...")
            self.upload_nzbs_to_premiumize_downloader()

            logger.debug("Checking for finished cloud downloads ...")
            self.check_premiumize_downloader_state()

            logger.debug("Checking if there are files to download to local ...")
            self.download_files_from_premiumize()

            logger.debug("Checking if there are files to clean up in the cloud ...")
            self.cleanup_online_files()

            logger.debug("Checking if there are files to move to done folder ...")
            self.move_to_done()

            logger.debug(f"Sleeping for {self.chk_delay}s ...\n")
            sleep(self.chk_delay)

    @retry(stop=tries(5), wait=w_exp(2, max=30), retry_error_callback=rh.on_fail, before_sleep=rh.on_retry)
    def move_to_done(self):
        q = "SELECT id, nzb_name, category_path, full_path FROM data WHERE state = 'downloaded and online cleaned up'"
        items = self.db.cursor.execute(q).fetchall()
        for item in items:
            d_id, d_name, category, nzb_full_path = item
            category = category[1:] if category.startswith("/") else category  # normalize category path

            logger.info(f"Moving files to done folder for {d_name} ...")
            try:
                src, dst = f"{self.dl_path}/{d_name}", f"{self.done_path}/{category}/{d_name}"
                self.fm.move_and_integrate(src, dst, d_id)
                done_at = UTCDateTime().str()
                self.db.cursor.execute("UPDATE data SET state = 'done', done_at = ? WHERE id = ?", (done_at, d_id))
                self.db.conn.commit()
                logger.info(f"COMPLETED {d_name}")
            except Exception as e:
                self.restore_state()  # state could be updated on error case
                raise e  # reraise the exception to retry this move step

            # if the nzb file can't be moved we don't want to retry the whole process...
            self.fm.move_and_integrate(nzb_full_path, f"{self.config_path}/archive/{d_name}")  # the nzb file

    @retry(stop=tries(3), wait=w_exp(2, min=5, max=45), retry_error_callback=rh.on_fail, before_sleep=rh.on_retry)
    def cleanup_online_files(self):
        q = "SELECT id, dl_id, nzb_name FROM data WHERE state = 'downloaded'"
        for item in self.db.cursor.execute(q).fetchall():
            d_id, dl_id, d_name = item
            logger.info(f"Removing files from premiumize cloud for {d_name} ...")
            try:
                self.pm.delete_transfer(dl_id)
            except RetryError as e:
                logger.error(f"Failed to delete transfer: {e}\n  Assuming it was already deleted ...")

            self.db.cursor.execute("UPDATE data SET state = 'downloaded and online cleaned up' WHERE id = ?", (d_id,))
            self.db.conn.commit()

    @retry(stop=tries(2), wait=w_exp(10, min=5, max=45), retry_error_callback=rh.on_fail, before_sleep=rh.on_retry)
    def download_files_from_premiumize(self):
        while self.to_download:
            (d_id, d_name, d_folder_id), category = self.to_download[0]
            try:
                category = category[1:] if category.startswith("/") else category  # normalize category path
                links_and_paths: list[tuple[str, str]] = self.get_folder_as_download_links(d_folder_id, d_name)
                for link, path, name in links_and_paths:
                    self.dl.dest = f"{self.dl_path}/{path}"
                    logger.info(f'Downloading: "{self.dl_path}/{path}/{name}" from {link[:40]}...')
                    self.dl.download(url=link, name=name)

                logger.info(f"Downloaded all files from {d_name} ...")
                logger.info(f"Removing the transfer from premiumize cloud and downloader for {d_name} ...")

                q = "UPDATE data SET state = 'downloaded' WHERE id = ?"
            except StateRetryError as e:  # only on StateRetryError we degrade the state
                logger.error(f"Failed to download files: {e}\n  degrading state to 'found'")
                q = "UPDATE data SET state = 'found' WHERE id = ?"

            self.db.cursor.execute(q, (d_id,))
            self.db.conn.commit()
            self.to_download.pop(0)

    @retry(stop=tries(3), wait=w_exp(2, min=5, max=20), retry_error_callback=rh.on_state_fail, before_sleep=rh.on_retry)
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
    @retry(stop=tries(3), wait=w_exp(max=10), retry_error_callback=rh.on_fail, before_sleep=rh.on_retry)
    def check_folder_for_incoming_nzbs(self):
        for root, _, files in os.walk(self.blackhole_path):
            for file in files:
                full_file_path = f"{root}/{file}"
                q = "SELECT * FROM data WHERE full_path = ?"
                already_tracked = self.db.cursor.execute(q, (full_file_path,)).fetchone()

                if already_tracked:
                    continue
                if file.endswith(".nzb"):
                    category_path = root[len(self.blackhole_path) :]
                    logger.info(f'Found new NZB file: "{file}" in subfolder: "{category_path}"')

                    self.db.cursor.execute(
                        "INSERT INTO data (nzb_name, state, full_path, category_path) VALUES (?, ?, ?, ?)",
                        (file, "found", full_file_path, category_path),
                    )
                    self.db.conn.commit()

                    self.to_premiumize.append((full_file_path, category_path))
                else:
                    logger.info(f"Found non-NZB file: {file} - ignoring")

    @retry(stop=tries(3), wait=w_exp(min=2, max=30), retry_error_callback=rh.on_fail, before_sleep=rh.on_retry)
    def upload_nzbs_to_premiumize_downloader(self):
        while self.to_premiumize:
            try:
                nzb_path, category_path = self.to_premiumize[0]
                logger.info(f"Uploading NZB file: {nzb_path} ...")

                dl_id = self.pm.upload_nzb(nzb_path, self.premiumarr_root_id)
                cld_dl_timeout_time = UTCDateTime(offset=timedelta(minutes=25)).str()

                q = "UPDATE data SET state = 'uploaded', dl_id = ?, cld_dl_timeout_time = ? WHERE full_path = ?"
                self.db.cursor.execute(q, (dl_id, cld_dl_timeout_time, nzb_path))
                self.db.conn.commit()

                self.to_watch[dl_id] = [0, category_path]
                self.to_premiumize.pop(0)
                logger.info(f"Uploaded NZB file: {nzb_path}")
            except FileNotFoundError:  # this is a critical error, we can't recover from this
                logger.error(f"PERMANENTLY FAILED: File was never found: {nzb_path}")
                # if the file is gone we will never be able to upload it, but technically this should not doom the nzb
                # file itself since if we had it we could try to process it ->
                # TODO:  notify sonarr to request it again (without marking it as forbidden)
                # for now we just mark it as failed
                q = "UPDATE data SET state = 'failed' WHERE full_path = ?"
                self.db.cursor.execute(q, (nzb_path,))
                self.db.conn.commit()
                self.to_premiumize.pop(0)

    @retry(stop=tries(3), wait=w_exp(min=2, max=30), retry_error_callback=rh.on_fail, before_sleep=rh.on_retry)
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
        filtered_ours = [item for item in transfers if item.id in self.to_watch]
        filtered_finished = [item for item in filtered_ours if item.status == "finished"]
        filtered_failed = [item for item in filtered_ours if item.status in retry_cases]
        filtered_waiting = [item for item in filtered_ours if item not in filtered_finished + filtered_failed]
        somehow_lost_ids = [item for item in self.to_watch if not any(item == x.id for x in filtered_ours)]

        for item in filtered_finished:
            category_path = self.to_watch[item.id][1]

            self.db.cursor.execute("SELECT id FROM data WHERE dl_id = ?", (item.id,))  # I much rather use the id
            d_id = self.db.cursor.fetchone()[0]

            q = "UPDATE data SET state = 'in premiumize cloud', dl_folder_id = ? WHERE id = ?"
            self.db.cursor.execute(q, (item.folder_id, d_id))
            self.db.conn.commit()

            self.to_download.append(((d_id, item.name, item.folder_id), category_path[1]))
            logger.info(f"Added item to download list: {item}")

            self.to_watch.pop(item.id)
            logger.info(f"Removed item from watch list: {item}")

        for item in filtered_failed:
            self.to_watch[item.id][0] += 1  # increase retry_count
            q = "SELECT id, full_path FROM data WHERE dl_id = ?"
            d_id, full_path = self.db.cursor.execute(q, (item.id,)).fetchone()[0]
            self.db.increment_dl_retry_count(d_id)

            cur_retry_count = self.to_watch[item.id][0]

            if cur_retry_count >= MAX_RETRY_COUNT:
                # TODO: Do we really want to handle this here already?
                logger.error(f'premiumize failed for: "{item}", notifying sonarr (NOT IMPL. YET)...')  # TODO: IMPL.
                self.db.mark_as_failed(d_id)
                # TODO: Add a stage where nzbs for failed items are deleted and also from the cloud
                try:
                    self.pm.delete_transfer(item.id)
                    shutil.move(full_path, f"{self.config_path}/archive/{item.name}")  # move the nzb to the archive
                except (FileNotFoundError, RetryError) as e:
                    logger.error(f"Failed to delete/Remove transfer/NZB: {e}\n  Assuming it was already deleted ...")

                self.to_watch.pop(item.id)
                continue

            logger.warning(f"Item failed to download ({cur_retry_count}/{MAX_RETRY_COUNT}): retrying ... {item}")
            self.pm.retry_transfer(item.id)  # unknown errors are resolvable by retrying on premiumize downloader

        # Print the status of the transfers that are still in progress
        for item in filtered_waiting:
            # get item infos:
            q = (
                "SELECT id, cld_dl_timeout_time, cld_dl_move_retry_c, full_path, category_path, message "
                + "FROM data WHERE dl_id = ?"
            )
            d_id, c_dc_timeout_time, cld_dl_move_retry_c, full_pth, cat_pth, last_message = self.db.cursor.execute(
                q, (item.id,)
            ).fetchone()

            # check first 3 chars e.g. 12%( of...), 100(% of...), Mov(ing to cloud)
            if str(item.message)[0:3] != last_message[0:3]:  # progress was made
                new_timeout_time = UTCDateTime(offset=timedelta(minutes=15)).str()
                c_dc_timeout_time = new_timeout_time
                self.db.set_message_and_timeout_time(d_id, item.message, new_timeout_time)

            if UTCDateTime() > UTCDateTime(from_str=c_dc_timeout_time):
                if item.message != "Moving to cloud":  # stuck in smth. else? e.g. 'Waiting for free upload slot' ?
                    logger.error(f"Transfer stuck: {item.name} at unexpected state '{item.message}' !PLS REPORT THAT!")
                    continue

                logger.error(f"TRANSFER TIMED OUT: {item.name}")
                if cld_dl_move_retry_c >= MAX_CLOUD_DL_MOVE_RETRY_COUNT:
                    logger.error(f"Cloud move retries exceeded for {item.name}, notifying sonarr (NOT IMPL. YET) ...")
                    # mark it as failed
                    self.db.mark_as_failed(d_id)
                    self.to_watch.pop(item.id)
                    continue
                    # TODO: IMPL. notify sonarr

                self.pm.delete_transfer(item.id)  # remove the transfer from the cloud
                # reset the state so it will be uploaded again but increase the retry count
                self.db.reset_to_found(d_id, cld_dl_move_retry_c_add=1)
                self.to_watch.pop(item.id)  # remove the transfer from the watch list
                self.to_premiumize.append((full_pth, cat_pth))  # add it to the DL list again
                continue

            logger.info("In progress:")
            logger.info(f'  name:"{item.name}", msg: "{item.message}"')

        for transfer_id in somehow_lost_ids:
            q = "SELECT id, nzb_name, full_path, category_path FROM data WHERE dl_id = ?"
            d_id, name, full_path, category_path = self.db.cursor.execute(q, (transfer_id,)).fetchone()

            logger.error(f"Transfer LOST: {name} was lost! Increasing retry count ...")
            self.db.reset_to_found(d_id, cld_dl_move_retry_c_add=1)
            self.to_watch.pop(transfer_id)  # remove the transfer from the watch list
            self.to_premiumize.append((full_path, category_path))
