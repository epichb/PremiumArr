import os
from time import sleep
import random
import requests

BASE_URL = "https://www.premiumize.me/api"  # https://app.swaggerhub.com/apis-docs/premiumize.me/api
SLEEP_TIMES = [5, 10, 30, 60, 120]
SLEEP_TRIES = len(SLEEP_TIMES)


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

    def get_account_info(self):
        return self._get("/account/info")

    def get_transfers(self):
        return TransferListResponse(self._get("/transfer/list"))

    def get_folder(self, f_id: str):
        return self._get(f"/folder/list?id={f_id}")

    def create_folder(self, name: str, parent_id: str = None):
        data = {"name": name}
        if parent_id:
            data["parent_id"] = parent_id
        return self._post("/folder/create", data=data)

    def list_folder(self, folder_id: str) -> FolderListResponse:
        return FolderListResponse(self._get(f"/folder/list?id={folder_id}"))

    def list_root_folder(self):
        return FolderListResponse(self._get("/folder/list"))

    def delete_folder(self, f_id: str):
        return self._post("/folder/delete", data={"id": f_id})

    def delete_item(self, f_id: str):
        return self._post("/item/delete", data={"id": f_id})

    def retry_transfer(self, transfer_id: str):
        return self._post("/transfer/retry", data={"id": transfer_id})

    def create_transfer(self, src: str, folder_id: str = None):
        data = {"src": src}
        if folder_id:
            data["folder_id"] = folder_id
        return self._post("/transfer/create", data=data)

    def delete_transfer(self, transfer_id: str):
        return self._post("/transfer/delete", data={"id": transfer_id})

    def clear_all_finished_transfers(self):
        return self._post("/transfer/clearfinished", data={})

    def _get(self, url: str):
        params = {"apikey": self.api_key}

        if url.startswith("/"):
            url = BASE_URL + url

        response = requests.get(url, params=params, timeout=90)
        if response.status_code != 200:
            raise RuntimeError(f"Request failed with status code {response.status_code}, {response.text}")
        return response.json()

    def _post(self, url: str, data: dict, files: dict = None):
        if url.startswith("/"):
            url = BASE_URL + url

        data["apikey"] = self.api_key

        response = requests.post(url, data=data, timeout=90, files=files)
        if response.status_code != 200:
            raise RuntimeError(f"Request failed with status code {response.status_code}, {response.text}")
        return response.json()

    def ensure_directory_exists(self, directory: str) -> None:
        create_folder_response = self.create_folder(directory)
        if (
            create_folder_response["status"] != "success"
            and create_folder_response["message"] != "This folder already exists."
        ):
            raise RuntimeError(f"Could not ensure directory exists: {create_folder_response}")

        # find the folder id
        root_folder = self.list_root_folder()
        for item in root_folder.content:
            if item.name != directory:
                continue
            return item.id
        raise RuntimeError(f"Could not find folder id (even though it should exist) for {directory}")

    def clear_folder(self, directory_id: str) -> None:
        folder = self.list_folder(directory_id)

        for item in folder.content:
            if item.is_folder():
                self.clear_folder(item.id)
            else:
                self.delete_item(item.id)

    def expect_fail_msg(self, response: dict, msg: str) -> None:
        if response["status"] != "success" and "message" in response and response["message"] == msg:
            return True
        return False

    def upload_nzb(self, nzb_path: str, target_folder_id: str):
        with open(nzb_path, "r+b") as f:
            i = 0
            while i <= SLEEP_TRIES:
                print(f"Uploading (try {i+1}/{SLEEP_TRIES}) {nzb_path} to premiumize downloader ...")
                resp = self._post("/transfer/create", data={"folder_id": target_folder_id}, files={"file": f})

                if self.expect_fail_msg(resp, "You have already added this nzb file."):
                    print("Already uploaded this nzb... circumventing the duplicate check, free retry!")
                    f.seek(0, os.SEEK_END)  # seek to the end of the file
                    f.write(b" " * random.randint(1, 100))  # append spaces to circumvent the premiumize duplicate check
                    f.seek(0)
                    i -= 1  # retry the upload, this error should not count, we can solve this kind of error
                elif resp["status"] == "success":
                    break
                # IMPROVEMENT IDEA: Add a check for "Network error" and busy wait till the network is back up
                else:
                    print(f"Failed to upload nzb: {resp}, sleeping for {SLEEP_TIMES[i]} seconds")
                    sleep(SLEEP_TIMES[i])

                i += 1

            assert "id" in resp, f"ERROR: After {SLEEP_TRIES} tries failed to upload nzb: {resp}"
            return resp["id"]
