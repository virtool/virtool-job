import json
from operator import itemgetter
from pathlib import Path
from typing import List

import aiofiles
import aiohttp

from virtool_workflow.abc.data_providers import AbstractHmmsProvider
from virtool_workflow.api.errors import raising_errors_by_status_code
from virtool_workflow.data_model import HMM


def _hmm_from_dict(hmm_json) -> HMM:
    return HMM(
        *itemgetter("id", "cluster", "count", "entries",
                    "families", "genera", "hidden",
                    "mean_entropy", "total_entropy",
                    "names")(hmm_json)
    )


class HmmsProvider(AbstractHmmsProvider):

    def __init__(self,
                 http: aiohttp.ClientSession,
                 jobs_api_url: str,
                 download_url: str,
                 work_path: Path):
        self.http = http
        self.url = f"{jobs_api_url}/hmm"
        self.download_url = f"{download_url}/hmms"
        self.path = work_path / "hmms"

        self.path.mkdir(parents=True, exist_ok=True)

    async def get(self, hmm_id: str):
        async with self.http.get(f"{self.url}/{hmm_id}") as response:
            async with raising_errors_by_status_code(response) as hmm_json:
                return _hmm_from_dict(hmm_json)

    async def hmm_list(self) -> List[HMM]:
        async with self.http.get(f"{self.url}/files/annotations.json.gz") as response:
            async with raising_errors_by_status_code(response, accept=[200]):
                async with aiofiles.open(self.path / "annotations.json", "wb") as f:
                    await f.write(await response.read())

        async with aiofiles.open(self.path / "annotations.json") as f:
            lines = await f.read()
            hmms_json = json.loads(lines)
            return [_hmm_from_dict(hmm) for hmm in hmms_json]

    async def get_profiles(self) -> Path:
        pass