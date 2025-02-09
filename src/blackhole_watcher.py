import os
import threading
from data.nzb import NZB
import pathlib
from manager import Manager


class BlackholeWatcher:
    def __init__(self, blackhole_path: pathlib.Path, manager: Manager, scan_interval=5):
        self.blackhole_path = blackhole_path
        self.manager = manager
        self.scan_interval = scan_interval
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            self.scan_blackhole()
            self.stop_event.wait(self.scan_interval)

    def scan_blackhole(self):
        # Check if there are files in the blackhole directory (recursively)
        for nzb_file in self.blackhole_path.rglob("*.nzb"):
            with open(nzb_file, "r") as file:
                nzb_data = file.read()
                nzb = NZB(nzb_file.name, nzb_data)

                # We expect the directory below the blackhole directory to be the category
                category = nzb_file.parent.relative_to(self.blackhole_path)

                self.manager.add_nzb(nzb, category)
            os.remove(nzb_file)

    def stop(self):
        self.stop_event.set()
