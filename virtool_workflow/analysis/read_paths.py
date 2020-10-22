"""Perform read prep before accessing Virtool reads_path"""
# pylint: disable=redefined-outer-name
import asyncio
import shutil
from pathlib import Path
from typing import List, Dict, Any, Tuple

import virtool_workflow
from virtool_workflow.analysis import utils, fastqc
from virtool_workflow.analysis.analysis_info import AnalysisArguments
from virtool_workflow.analysis.cache import fetch_cache, prepare_reads_and_create_cache
from virtool_workflow.execute import FunctionExecutor
from virtool_workflow.storage.utils import copy_paths
from virtool_workflow_runtime.db import VirtoolDatabase


def rename_trimming_results(path: Path):
    """
    Rename Skewer output to a simple name used in Virtool.

    :param path: The path containing the results from Skewer
    """
    try:
        shutil.move(
            path/"reads-trimmed.fastq.gz",
            path/"reads_1.fq.gz",
        )
    except FileNotFoundError:
        shutil.move(
            path/"reads-trimmed-pair1.fastq.gz",
            path/"reads_1.fq.gz",
        )

        shutil.move(
            path/"reads-trimmed-pair2.fastq.gz",
            path/"reads_2.fq.gz",
        )

    shutil.move(
        path/"reads-trimmed.log",
        path/"trim.log",
    )


@virtool_workflow.fixture
async def parsed_fastqc(
        trimming_output: Tuple[Path, str],
        analysis_args: AnalysisArguments,
        number_of_processes: int,
):
    trimming_output_path, _ = trimming_output

    rename_trimming_results(trimming_output_path)

    read_paths = utils.make_read_paths(trimming_output_path, analysis_args.paired)

    fastqc_path = analysis_args.temp_cache_path/"fastqc"
    fastqc_path.mkdir()

    await fastqc.run_fastqc(number_of_processes, read_paths, fastqc_path)

    return fastqc.parse_fastqc(fastqc_path, analysis_args.sample_path)


async def fetch_legacy_paths(
        paths: List[Path],
        reads_path: Path,
        run_in_executor: FunctionExecutor
):
    coroutines = [
        run_in_executor(shutil.copy, path, reads_path/path.name)
        for path in paths
    ]

    await asyncio.gather(*coroutines)


@virtool_workflow.fixture
async def reads_path(
        analysis_args: AnalysisArguments,
        cache_path: Path,
        cache_document: Dict[str, Any],
        database: VirtoolDatabase,
        trimming_parameters: Dict[str, Any],
        trimming_command: List[str],
        number_of_processes: int,
        run_in_executor: FunctionExecutor
) -> Path:
    """The analysis reads path with caches fetched if they exist."""
    analysis_args.reads_path.mkdir(parents=True, exist_ok=True)

    if cache_document:
        await fetch_cache(cache_document,
                          cache_path,
                          analysis_args.reads_path,
                          run_in_executor)

    elif not all(f["raw"] for f in analysis_args.sample["files"]):
        legacy_paths = utils.make_legacy_read_paths(analysis_args.sample_path, analysis_args.paired)

        paths_to_copy = {path: reads_path/path.name
                         for path in legacy_paths}

        await copy_paths(paths_to_copy.items(), run_in_executor)
    else:
        await prepare_reads_and_create_cache(analysis_args,
                                             trimming_parameters,
                                             trimming_command,
                                             cache_path,
                                             number_of_processes,
                                             database,
                                             run_in_executor)

    return analysis_args.reads_path
