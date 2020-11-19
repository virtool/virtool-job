"""Create caches of read-prep steps for Virtool analysis workflows."""
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

import virtool_core.caches.db
import virtool_core.samples.db
from virtool_workflow import fixture
from virtool_workflow.analysis import utils
from virtool_workflow.analysis.analysis_info import AnalysisArguments
from virtool_workflow.execute import FunctionExecutor
from virtool_workflow.storage.utils import copy_paths
from virtool_workflow_runtime.db import VirtoolDatabase
from virtool_workflow_runtime.db.fixtures import Collection

TRIMMING_PROGRAM = "skewer-0.2.2"


@fixture
async def cache_document(
        trimming_parameters: Dict[str, Any],
        sample_id: str,
        caches: Collection,
) -> Optional[Dict[str, Any]]:
    """
    The cache document for the current analysis.

    If no cache exists (ie. the current analysis job is not a re-try) then None is returned.
    """
    cache_document = await caches.find_one({
        "hash": virtool_core.caches.db.calculate_cache_hash(trimming_parameters),
        "missing": False,
        "program": TRIMMING_PROGRAM,
        "sample.id": sample_id,
    })

    if cache_document:
        cache_document["id"] = cache_document["_id"]

    return cache_document


async def fetch_cache(
        cache_document: Dict[str, Any],
        cache_path: Path,
        reads_path: Path,
        run_in_executor: FunctionExecutor
):
    """Copy cached read files to the reads_path."""
    cached_read_paths = utils.make_read_paths(
        reads_dir_path=cache_path/cache_document["_id"],
        paired=cache_document["paired"]
    )

    await copy_paths(
        {path: reads_path/path.name for path in cached_read_paths}.items(),
        run_in_executor
    )


async def create_cache_document(
        database: VirtoolDatabase,
        analysis_args: AnalysisArguments,
        trimming_parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a new cache document in the database.

    This document will be used to check for the presence of cached prepared reads.

    :param database: The Virtool database object
    :param analysis_args: The AnalysisArguments fixture
    :param trimming_parameters: The trimming parameters (see virtool_workflow.analysis.trimming)
    :return: The cache document which was created.
    """
    cache = await virtool_core.caches.db.create(
        database,
        analysis_args.sample_id,
        trimming_parameters,
        analysis_args.paired
    )

    await database["analyses"].update_one({"_id": analysis_args.analysis_id}, {
        "$set": {
            "cache": {
                "id": cache["id"]
            }
        }
    })

    return cache


async def create_cache(
        fastq: Dict[str, Any],
        database: VirtoolDatabase,
        analysis_args: AnalysisArguments,
        trimming_parameters: Dict[str, Any],
        trimming_output_path: Path,
        cache_path: Path,
):
    """
    Cache the trimmed reads and parsed fastqc data.

    :param fastq: The parsed fastqc data produced by #virtool_workflow.analysis.fastqc.parse_fastqc
        or the #virtool_workflow.analysis.read_paths.parsed_fastqc fixture.
    """
    cache = await create_cache_document(database, analysis_args, trimming_parameters)

    await database["caches"].update_one({"_id": cache["id"]}, {"$set": {
            "quality": fastq
        }
    })

    shutil.copytree(trimming_output_path, cache_path/cache["id"])


async def delete_cache_if_not_ready(cache_id: str, caches: Collection, cache_path: Path):
    """
    Delete a cache if it is not ready.

    :param cache_id: The database id of the cache document.
    :param caches: The caches database collection for Virtool.
    :param cache_path: The path to the cache entry which is to be removed.
    """
    cache = await caches.find_one(cache_id, ["ready"])

    if not cache["ready"]:
        await caches.delete_one({"_id": cache_id})

        try:
            shutil.rmtree(cache_path)
        except FileNotFoundError:
            pass


async def delete_analysis(analysis_id: str, analysis_path: Path, sample_id: str, database: VirtoolDatabase):
    """
    Delete the analysis associated to `analysis_id`.

    Intended to be called upon failure of an analysis workflow.

    :param analysis_id: The database id of the analysis document.
    :param analysis_path: The virtool analysis path.
    :param analyses: The analyses database collection.
    """

    analyses = database["analyses"]

    await analyses.delete_one({"_id": analysis_id})

    try:
        shutil.rmtree(analysis_path)
    except FileNotFoundError:
        pass

    await virtool_core.samples.db.recalculate_workflow_tags(database, sample_id)

