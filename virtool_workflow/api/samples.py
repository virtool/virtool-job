from pathlib import Path
from typing import Dict, Any

import aiohttp

from virtool_workflow.abc.data_providers import AbstractSampleProvider
from virtool_workflow.api.errors import raising_errors_by_status_code
from virtool_workflow.data_model import Sample
from virtool_workflow.data_model.files import VirtoolFileFormat


class SampleProvider(AbstractSampleProvider):

    def __init__(self,
                 sample_id: str,
                 http: aiohttp.ClientSession,
                 jobs_api_url: str):
        self.id = sample_id
        self.http = http
        self.url = f"{jobs_api_url}/samples/{sample_id}"

    async def get(self) -> Sample:
        async with self.http.get(self.url) as response:
            async with raising_errors_by_status_code(response) as sample_json:
                return Sample(
                    id=sample_json["id"],
                    name=sample_json["name"],
                    host=sample_json["host"],
                    isolate=sample_json["isolate"],
                    locale=sample_json["locale"],
                    library_type=sample_json["library_type"],
                    paired=sample_json["paired"],
                    quality=sample_json["quality"],
                    nuvs=sample_json["nuvs"],
                    pathoscope=sample_json["pathoscope"],
                    files=sample_json["files"],
                )

    async def finalize(self, quality: Dict[str, Any]) -> Sample:
        pass

    async def delete(self):
        pass

    async def upload(self, path: Path, format: VirtoolFileFormat):
        pass

    async def download(self):
        pass


async def release_files(self):
    pass
