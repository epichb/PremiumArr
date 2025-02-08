import random
import string
from werkzeug.datastructures import FileStorage


class SabnzbdApi:
    def __init__(self):
        self.queue = []
        self.history = []

    def get_version(self):
        return {"version": "4.4.1"}

    def get_config(self):
        return {
            "config": {
                "misc": {
                    "complete_dir": "/complete/dir",
                    "tv_categories": ["tv", "Series"],
                    "enable_tv_sorting": True,
                    "movie_categories": ["Movies", "Films"],
                    "enable_movie_sorting": True,
                    "date_categories": ["Date1", "Date2"],
                    "enable_date_sorting": False,
                    "pre_check": True,
                    "history_retention": "7 days",
                    "history_retention_option": "days",
                    "history_retention_number": 7,
                },
                "categories": [],
                "servers": [],
                "sorters": [],
            }
        }

    def get_queue(self):
        return {"queue": {"my_home": "/tmp", "paused": False, "slots": self.queue}}

    def get_history(self):
        return {"history": {"paused": False, "slots": []}}

    def add_file(self, data: FileStorage):
        # Create a random string to simulate an NZB ID
        random_string = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        self.queue.append(
            {
                "status": "Downloading",
                "index": len(self.queue) + 1,
                "timeleft": "1:00:00",
                "mb": "100",
                "filename": data.filename,
                "priority": "Normal",
                "cat": "",
                "mbleft": "20",
                "percentage": 80,
                "nzo_id": random_string,
            }
        )

        self.history.append(
            {
                "fail_message": "",
                "bytes": str(100 * 1024),
                "category": "",
                "nzb_name": data.filename,
                "download_time": 60,
                "storage": "/tmp",
                "status": "Downloading",
                "nzo_id": random_string,
                "name": data.filename,
            }
        )
        return {"status": True, "nzo_ids": [random_string]}
