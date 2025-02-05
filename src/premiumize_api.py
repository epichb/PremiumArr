import os
import random
import requests
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError  # retry_if_exception_type,
from src.helper import on_fail

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.premiumize.me/api"  # https://app.swaggerhub.com/apis-docs/premiumize.me/api
# IMPROVEMENT IDEA: Add a check for "Network error" and busy wait till the network is back up


class FolderFileResponse:
    """
    Class to represent a folder or file response from the API
    Only id, name, type, created_at are guaranteed to be present (for folders and files)
    For files you can also expect size, link and directlink
    """

    def __init__(self, data: dict):
        self.id = data["id"]
        self.name = data["name"]
        self.type = data["type"]
        self.created_at = data["created_at"]

        assert self.type in ["folder", "file"], f"Invalid type, expected file or folder but was: {self.type}"

        if self.type == "file":
            self.size = data["size"]
            self.directlink = data["directlink"]
            self.link = data["link"]

    def is_folder(self):
        return self.type == "folder"

    def is_file(self):
        return self.type == "file"

    def __str__(self):
        return f"{self.type}: {self.name} | (ID:{self.id})"


class FolderListResponse:
    """A class to represent a folder list response"""

    def __init__(self, data: dict):
        self.status = data["status"]
        self.content = [FolderFileResponse(item) for item in data.get("content", [])]
        self.name = data.get("name", None)
        self.parent_id = data.get("parent_id", None)
        self.folder_id = data.get("folder_id", None)

    def __str__(self):
        string = f"Folder list response: {self.status} - {len(self.content)} items:"
        for item in self.content:
            string += f"\n{str(item)}"
        return string


class TransferListResponse:
    """Has status [success, error] and transfers"""

    def __init__(self, data: dict):
        self.status = data["status"]
        self.transfers: list[TransItem] = [TransItem(item) for item in data.get("transfers", [])]


class TransItem:
    """
    has id, name, message (holds None, percent (0% of 000.00 MB. ETA is 00:00:00),
    status (waiting, finished, running, deleted, banned, error, timeout, seeding, queued),
    progress (float from 0 to 1), folder_id, src
    """

    def __init__(self, data: dict):
        assert "folder_id" in data, "Missing folder_id in transfer item, Invalid data, we expect a folder_id"
        self.id = data["id"]
        self.name = data["name"]
        self.message = data["message"]
        self.status = data["status"]
        self.progress = data["progress"]
        self.folder_id = data["folder_id"]
        self.src = data["src"]

    def __str__(self):
        return str(vars(self))


class PremiumizeAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=1, max=20), retry_error_callback=on_fail)
    def get_account_info(self):
        return self._get("/account/info")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=1, max=20), retry_error_callback=on_fail)
    def get_transfers(self) -> list[TransItem]:
        resp = TransferListResponse(self._get("/transfer/list"))
        if resp.status != "success":
            raise RetryError(f"Failed to get transfer list: {resp}")
        assert isinstance(resp, TransferListResponse), f"Expected type transfer_list_response, got {type(resp)}"
        return resp.transfers

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=1, max=20), retry_error_callback=on_fail)
    def create_folder(self, name: str, parent_id: str = None):
        data = {"name": name}
        if parent_id:
            data["parent_id"] = parent_id
        return self._post("/folder/create", data=data)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=1, max=20), retry_error_callback=on_fail)
    def list_folder(self, folder_id: str) -> FolderListResponse:
        f_list = FolderListResponse(self._get(f"/folder/list?id={folder_id}"))
        if f_list.status != "success":
            raise RetryError(f"Failed to list folder: {f_list}")
        return f_list

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=1, max=20), retry_error_callback=on_fail)
    def list_root_folder(self):
        return FolderListResponse(self._get("/folder/list"))

    # unused
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=1, max=20), retry_error_callback=on_fail)
    def delete_folder(self, f_id: str):
        return self._post("/folder/delete", data={"id": f_id})

    # unused
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=1, max=20), retry_error_callback=on_fail)
    def delete_item(self, f_id: str):
        return self._post("/item/delete", data={"id": f_id})

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(2, min=1, max=20), retry_error_callback=on_fail)
    def retry_transfer(self, transfer_id: str):
        response = self._post("/transfer/retry", data={"id": transfer_id})
        if response["status"] != "success":
            raise RetryError(f"Failed to retry transfer: {response}")
        return response

    # unused
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=1, max=20), retry_error_callback=on_fail)
    def create_transfer(self, src: str, folder_id: str = None):
        data = {"src": src}
        if folder_id:
            data["folder_id"] = folder_id
        return self._post("/transfer/create", data=data)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=1, max=20), retry_error_callback=on_fail)
    def delete_transfer(self, transfer_id: str):
        result = self._post("/transfer/delete", data={"id": transfer_id})
        if result["status"] != "success":
            raise RetryError(f"Failed to delete transfer: {result}")
        return result

    # unused
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=1, max=20), retry_error_callback=on_fail)
    def clear_all_finished_transfers(self):
        return self._post("/transfer/clearfinished", data={})

    def _get(self, url: str):
        params = {"apikey": self.api_key}
        url = BASE_URL + url if url.startswith("/") else url

        response = requests.get(url, params=params, timeout=90)
        if response.status_code != 200:
            raise RuntimeError(f"Request failed with status code {response.status_code}, {response.text}")
        return response.json()

    def _post(self, url: str, data: dict, files: dict = None):
        url = BASE_URL + url if url.startswith("/") else url
        data["apikey"] = self.api_key

        response = requests.post(url, data=data, timeout=90, files=files)
        if response.status_code != 200:
            raise RuntimeError(f"Request failed with status code {response.status_code}, {response.text}")
        return response.json()

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=60), retry_error_callback=on_fail)
    def ensure_directory_exists(self, directory: str) -> None:
        resp = self.create_folder(directory)
        if resp["status"] != "success" and resp["message"] != "This folder already exists.":
            raise RuntimeError(f"Could not ensure directory exists: {resp}")

        # find the folder id
        root_folder = self.list_root_folder()
        for item in root_folder.content:
            if item.name != directory:
                continue
            return item.id
        raise RuntimeError(f"Could not find folder id (even though it should exist) for {directory}")

    # unused
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=1, max=30), retry_error_callback=on_fail)
    def clear_folder(self, directory_id: str) -> None:
        folder = self.list_folder(directory_id)

        for item in folder.content:
            if item.is_folder():
                self.clear_folder(item.id)
            else:
                self.delete_item(item.id)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(2, min=1, max=20), retry_error_callback=on_fail)
    def expect_fail_msg(self, response: dict, msg: str) -> None:
        if response["status"] != "success" and "message" in response and response["message"] == msg:
            return True
        if response["status"] != "success" and "message" in response and response["message"] != msg:
            raise RetryError(f"Failed to upload nzb: {response}")  # Other error than the expected one
        return False  # success

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(2, min=2, max=120), retry_error_callback=on_fail)
    def upload_nzb(self, nzb_path: str, target_folder_id: str):
        with open(nzb_path, "r+b") as f:
            logger.warning(f"Uploading (try ) {nzb_path} to premiumize downloader ...")
            resp = self._post("/transfer/create", data={"folder_id": target_folder_id}, files={"file": f})

            while self.expect_fail_msg(resp, "You have already added this nzb file."):
                logger.warning("Already uploaded this nzb... circumventing the duplicate check, free retry!")
                f.seek(0, os.SEEK_END)  # seek to the end of the file
                f.write(b" " * random.randint(1, 100))  # append spaces to circumvent the premiumize duplicate check
                f.seek(0)
                resp = self._post("/transfer/create", data={"folder_id": target_folder_id}, files={"file": f})

            assert "id" in resp, f"Failed to upload nzb (missing id): {resp}"
            u_id = resp["id"]
            assert isinstance(u_id, str) and len(u_id) > 0, f"Failed to upload nzb (invalid id): {resp}"
            return u_id
