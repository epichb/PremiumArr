import os
import shutil
from time import sleep
from src.downloader import Downloader
from src.premiumize_api import PremiumizeAPI, TransferListResponse


class Manager:
    def __init__(self, api_key: str, paths: tuple, dl_threads: int, dl_speed: int, chk_delay: int):
        self.blackhole_path, self.dl_path, self.done_path = paths
        self.to_download, self.to_premiumize, self.to_remove_from_premiumize_cloud, self.to_watch = [], [], [], {}
        self.chk_delay = chk_delay

        self.pm = PremiumizeAPI(api_key)
        self.dl = Downloader(self.dl_path, dl_threads, dl_speed)

        self.test_basic_api_connection()

        self.premiumarr_root_id = self.pm.ensure_directory_exists("premiumarr")
        assert self.premiumarr_root_id, "Failed to get root folder ID"
        print("Manager finished init")

    def test_basic_api_connection(self):
        info = self.pm.get_account_info()
        print(f"Premiumize account info: {info}")
        assert info["status"] == "success", f"Failed to get account info, check your API key! (ERR: {info})"

    def run(self):
        while True:
            print("Checking for incoming NZBs ...")
            self.check_folder_for_incoming_nzbs()

            print("Uploading NZBs to premiumize downloader ...")
            self.upload_nzbs_to_premiumize_downloader()

            print("Checking for finished cloud downloads ...")
            self.check_premiumize_downloader_state()

            print("Checking if there are files to download to local ...")
            self.download_files_from_premiumize()

            print(f"Sleeping for {self.chk_delay}s ...\n")
            sleep(self.chk_delay)

    # TODO: think about mutex and persistence
    def download_files_from_premiumize(self):
        while self.to_download:
            item, category = self.to_download.pop()  # TODO: not good, its not done downloading yet, so don't remove it

            category = category[1:] if category.startswith("/") else category
            links_and_paths: list[tuple[str, str]] = self.get_folder_as_download_links(item.folder_id, item.name)
            for link, path, name in links_and_paths:
                self.dl.dest = f"{self.dl_path}/{path}"
                print(f"Downloading: '{self.dl_path}/{path}/{name}' from {link[:40]}...")
                self.dl.download(url=link, name=name)

            print(f"Downloaded all files from {item.name} ...")
            print(f"Removing the transfer from premiumize cloud and downloader for {item.name} ...")
            self.test_with_retry(lambda x: x["status"] == "success", self.pm.delete_transfer, item.id)

            # move the files to the done folder
            print(f"Moving files to done folder for {item.name} ...")
            os.makedirs(f"{self.done_path}/{category}", exist_ok=True)
            shutil.move(f"{self.dl_path}/{item.name}", f"{self.done_path}/{category}/{item.name}")
            print(f"COMPLETED {item.name}")

    def get_folder_as_download_links(self, f_id: str, path: str = "") -> list[tuple[str, str, str]]:
        ret = []
        folder = self.test_with_retry(lambda x: x.status == "success", self.pm.list_folder, f_id)
        for item in folder.content:
            if item.is_folder():
                ret.extend(self.get_folder_as_download_links(item.id, f"{path}/{item.name}"))
            elif item.is_file():
                ret.append((item.link, f"{path}", item.name))

        return ret

    # IDEA: maybe I can to check_folder_for_incoming_nzbs and upload_nzbs_to_premiumize_downloader in a single thread
    # that way I would not need to use a mutex to prevent others from modifying the list
    def check_folder_for_incoming_nzbs(self):
        # TODO: set mutex to prevent others from modifying the list
        for root, _, files in os.walk(self.blackhole_path):
            for file in files:
                if file.endswith(".nzb"):
                    path_without_blackhole = root[len(self.blackhole_path) :]
                    print(f"Found NZB file: {file} in subfolder: {path_without_blackhole}")
                    self.to_premiumize.append((f"{root}/{file}", path_without_blackhole))
                else:
                    print(f"Found non-NZB file: {file} - ignoring")
        # TODO: persist state to be persistent over crashes
        # TODO: remove mutex

    def upload_nzbs_to_premiumize_downloader(self):
        # TODO: set mutex to prevent others from modifying the list
        while self.to_premiumize:
            nzb_path, category_path = self.to_premiumize[0]
            print(f"Uploading NZB file: {nzb_path} ...")

            dl_id = self.test_with_retry(
                lambda x: len(x) > 0 and isinstance(x, str), self.pm.upload_nzb, nzb_path, self.premiumarr_root_id
            )

            self.to_watch[dl_id] = [0, category_path]
            self.to_premiumize.pop(0)
            # TODO: Persist state to be persistent over crashes

            os.remove(nzb_path)  # file is not needed anymore
            print(f"Uploaded and removed NZB file: {nzb_path}")
        # TODO: remove mutex

    def check_premiumize_downloader_state(self):
        def success_test(resp: TransferListResponse) -> bool:
            assert isinstance(resp, TransferListResponse), f"Expected type transfer_list_response, got {type(resp)}"
            return resp.status == "success"

        if len(self.to_watch) == 0:  # nothing to watch, so don't bother the API
            return

        transfers = self.test_with_retry(success_test, self.pm.get_transfers).transfers

        # TODO: REMOVE this DEBUG print
        # for item in transfers:
        #     print(f"Transfer: {item}")

        # TODO: set mutex to prevent others from modifying the list
        # filter the transfers that are in the to_watch list use
        filtered_to_watched = [item for item in transfers if item.id in self.to_watch.keys()]
        filtered_to_finished = [item for item in filtered_to_watched if item.status == "finished"]
        retry_cases = ["deleted", "banned", "error", "timeout"]
        filtered_to_failed = [item for item in filtered_to_watched if item.status in retry_cases]

        for item in filtered_to_finished:
            from_watch = self.to_watch[item.id]

            self.to_download.append((item, from_watch[1]))  # from_watch[1] == nzb_path
            # TODO: persist state to be persistent over crashes
            print(f"Added item to download list: {item}")

            self.to_watch.pop(item.id)
            # TODO: persist state to be persistent over crashes
            print(f"Removed item from watch list: {item}")

        for item in filtered_to_failed:
            self.to_watch[item.id][0] += 1  # from_watch[0] == retry_count
            cur_retry_count = self.to_watch[item.id][0]
            if cur_retry_count >= 6:
                # TODO: notify sonarr that the download failed
                print(f"Item failed to download: {item}, notifying sonarr ...")

            print(f"Item failed to download ({cur_retry_count}/6): retrying ... {item}")

            # TODO: persist state to be persistent over crashes
            self.test_with_retry(lambda x: x["status"] == "success", self.pm.retry_transfer, item.id)
            # unknown errors are resolvable by retrying on premiumize downloader

        progressing = [i for i in filtered_to_watched if i.status != "finished" and i.status not in retry_cases]
        for item in progressing:
            print(f"{item.name}: {item.message}")
        # TODO: remove mutex

    def test_with_retry(self, success_tester: callable, func: callable, *args, n_retries: int = 6, **kwargs):
        for i in range(n_retries):
            print(f"Trying to execute {func.__name__} with args {args} and kwargs {kwargs} ... (try {i+1}/{n_retries})")
            try:
                result = func(*args, **kwargs)
                if success_tester(result):
                    return result
                print("Test for success failed, retrying ...")

            except Exception as e:  # pylint: disable=broad-except # we intentionally catch all exceptions
                print(f"Failed to execute {func.__name__} with args {args} and kwargs {kwargs}, retrying ...")
                print(f"Exception: {e}")
            sleep(5 * i)
        raise RuntimeError(f"Failed to execute {func.__name__} with args {args} and kwargs {kwargs} after 6 tries")
        # TODO: what to do if it fails 6 times?
