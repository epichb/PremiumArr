from data.nzb import NZB
from helper import UTCDateTime


class PremiumizeMeMetadata:
    def __init__(
        self,
        download_id: int,
        download_retry_count: int,
        folder_id: int,
        message: str,
        timeout_time: UTCDateTime,
        move_retry_count: int,
    ):
        self.download_id = download_id
        self.download_retry_count = download_retry_count
        self.folder_id = folder_id
        self.message = message
        self.timeout_time = timeout_time
        self.move_retry_count = move_retry_count


class Job:
    def __init__(
        self,
        job_id: int,
        state: str,
        created_at: UTCDateTime,
        done_at: UTCDateTime,
        category: str,
        state_retry_count: int,
        prem_metadata: PremiumizeMeMetadata,
        nzb: NZB,
    ):
        self.job_id = job_id
        self.state = state
        self.created_at = created_at
        self.done_at = done_at
        self.category = category
        self.prem_metadata = prem_metadata
        self.nzb = nzb
        self.state_retry_count = state_retry_count
