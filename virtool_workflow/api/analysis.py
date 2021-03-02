import logging
from pathlib import Path
from typing import Dict, Any

import aiofiles
import aiohttp
import dateutil.parser
from aiohttp import ContentTypeError
from virtool_workflow.abc.data_providers import AbstractAnalysisProvider
from virtool_workflow.api.errors import InsufficientJobRights, JobsAPIServerError, NotFound, AlreadyFinalized
from virtool_workflow.data_model.analysis import Analysis
from virtool_workflow.data_model.files import AnalysisFile, VirtoolFileFormat

logger = logging.getLogger(__name__)


def _analysis_file_from_api_response_json(json):
    return [
        AnalysisFile(
            id=f["id"],
            name=f["name"],
            name_on_disk=f["name_on_disk"],
            size=f["size"],
            uploaded_at=dateutil.parser.isoparse(f["uploaded_at"]),
            format=f["format"]
        )
        for f in json["files"]
    ]


async def get_analysis_by_id(analysis_id: str, http: aiohttp.ClientSession, jobs_api_url: str) -> Analysis:
    """
    Get the analysis by id via the jobs API.

    :param analysis_id: The id of the analysis.
    :param http: A :class:`aiohttp.ClientSession` instance.
    :param jobs_api_url: The url for the jobs API server.

    :return: A :class:`virtool_workflow.data_model.analysis.Analysis` instance.

    :raise JobsAPIServerError: When the jobs API server fails to respond with a JSON body
    :raise InsufficientJobRights: When the current job does not have sufficient rights to access the analysis.
    :raise NotFound: When the given :obj:`analysis_id` does not correspond to an existing analysis (HTTP 404).
    """
    async with http.get(f"{jobs_api_url}/analyses/{analysis_id}") as response:
        try:
            response_json = await response.json()

            return Analysis(
                id=response_json["id"],
                files=_analysis_file_from_api_response_json(response_json),
            )
        except aiohttp.ContentTypeError:
            raise JobsAPIServerError(response.status)
        except KeyError:
            if response.status == 203:
                raise InsufficientJobRights(response_json, response.status)
            elif response.status == 404:
                raise NotFound(response_json, response.status)


async def upload_analysis_file(analysis_id: str,
                               path: Path,
                               format: VirtoolFileFormat,
                               http: aiohttp.ClientSession,
                               jobs_api_url: str):
    """Upload an analysis file using the jobs API."""
    with path.open('rb') as binary:
        async with http.post(f"{jobs_api_url}/analyses/{analysis_id}/files", data={"file": binary}, params={
            "name": path.name,
            "format": format
        }) as response:
            try:
                response_json = await response.json()
            except aiohttp.ContentTypeError as content_type_error:
                raise JobsAPIServerError(response.status) from content_type_error

            try:
                return AnalysisFile(
                    id=response_json["id"],
                    name=response_json["name"],
                    name_on_disk=response_json["name_on_disk"],
                    size=response_json["size"],
                    uploaded_at=dateutil.parser.isoparse(response_json["uploaded_at"]),
                    format=response_json["format"],
                )
            except KeyError as key_error:
                if response.status in (400, 409):
                    raise ValueError(response_json) from key_error
                elif response.status == 403:
                    raise InsufficientJobRights(response_json) from key_error
                elif response.status == 404:
                    raise NotFound(response_json) from key_error
                else:
                    raise JobsAPIServerError(response_json) from key_error


class AnalysisProvider(AbstractAnalysisProvider):
    def __init__(self,
                 analysis_id: str,
                 http: aiohttp.ClientSession,
                 jobs_api_url: str,
                 work_path: Path):
        self.id = analysis_id
        self.http = http
        self.api_url = jobs_api_url
        self.work_path = work_path

    async def get(self) -> Analysis:
        return await get_analysis_by_id(self.id, self.http, self.api_url)

    async def upload(self, path: Path, format: VirtoolFileFormat):
        return await upload_analysis_file(self.id, path, format, self.http, self.api_url)

    async def download(self, file_id: str, target_path: Path = None) -> Path:
        """
        Download a file associated to the current analysis.

        :param file_id: The ID of the file.
        :param target_path: The path which the file data should be stored under.
        :return: A path to the downloaded file. It will be the `target_path` if one was given.
        :raise NotFound: When either the file or the analysis does not exist (404 status code).
        :raise JobsAPIServerError: When the status code of the response is not 200 or 404.
        """
        target_path = target_path or self.work_path

        async with self.http.get(f"{self.api_url}/analyses/{self.id}/files/{file_id}") as response:
            if response.status == 200:
                async with aiofiles.open(target_path, "wb") as f:
                    await f.write(await response.read())

                return target_path
            elif response.status == 404:
                raise NotFound(await response.json())

            raise JobsAPIServerError(await response.json())

        return target_path

    async def upload_result(self, result: Dict[str, Any]):
        pass

    async def delete(self):
        """
        Delete the analysis. This method should be called if the workflow code fails before a result is uploaded.

        :raise InsufficientJobRights: When the current job does not have the appropriate permissions required
            to delete the analysis.
        :raise NotFound: When the analysis has already been deleted.
        :raise AlreadyFinalized: When the analysis has a result uploaded and is viewable in Virtool.
            Jobs are not permitted to delete the analysis after this point.
        :raise JobsAPIServerError: When the analysis is not deleted for any other reason.
        """
        async with self.http.delete(f"{self.api_url}/analyses/{self.id}") as response:
            if response.status == 204:
                return

            try:
                response_json = await response.json()
                response_message = response_json["message"]
            except ContentTypeError:
                response_message = await response.text()
            except KeyError:
                response_message = response_json

            if response.status == 403:
                raise InsufficientJobRights(response_message)
            elif response.status == 404:
                raise NotFound(response_message)
            elif response.status == 409:
                raise AlreadyFinalized(response_message)
            else:
                raise JobsAPIServerError(response_message)
