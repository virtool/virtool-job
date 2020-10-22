import os
import shutil
import filecmp
from contextlib import contextmanager
from pathlib import Path

import pytest

from . import fastqc_out

from virtool_workflow.analysis import utils
from virtool_workflow.analysis.analysis_info import AnalysisArguments, AnalysisInfo
from virtool_workflow.analysis.library_types import LibraryType
from virtool_workflow.analysis.read_paths import reads_path
from virtool_workflow.analysis.trim_parameters import trimming_parameters
from virtool_workflow.storage.paths import context_directory
from virtool_workflow.workflow_fixture import WorkflowFixtureScope
from virtool_core.db import Collection
from virtool_workflow.analysis.cache import cache_document
from virtool_workflow.analysis.trimming import trimming_output, trimming_output_path, trimming_input_paths
from virtool_workflow.analysis.read_paths import parsed_fastqc

TEST_ANALYSIS_INFO = AnalysisInfo(
        sample_id="1",
        index_id="1",
        ref_id="1",
        analysis_id="1",
        sample=dict(
            _id="1",
            paired=False,
            library_type=LibraryType.amplicon,
            quality=dict(
                length=["", "1"],
                count="3"
            ),
            files=[dict(raw=True)],
        ),
        analysis=dict(
            subtraction=dict(id="id with spaces")
        )
    )


@pytest.yield_fixture
def fixtures():
    with WorkflowFixtureScope() as _fixtures:
        _fixtures["job_id"] = "1"
        _fixtures["analysis_info"] = TEST_ANALYSIS_INFO
        _fixtures["data_path"] = Path("virtool")
        _fixtures["number_of_processes"] = 3
        with context_directory(Path("temp")) as temp:
            _fixtures["temp_path"] = temp

            yield _fixtures


async def test_analysis_fixture_instantiation(fixtures):
    arguments: AnalysisArguments = await fixtures.instantiate(AnalysisArguments)

    assert fixtures["analysis_args"] == arguments

    assert arguments.analysis == TEST_ANALYSIS_INFO.analysis
    assert arguments.sample == TEST_ANALYSIS_INFO.sample
    assert not arguments.paired
    assert arguments.read_count == 3
    assert arguments.sample_read_length == 1
    assert arguments.sample_path == fixtures["data_path"]/"samples/1"
    assert arguments.path == arguments.sample_path/"analysis/1"
    assert arguments.index_path == fixtures["data_path"]/"references/1/1/reference"
    assert arguments.reads_path == fixtures["temp_path"]/"reads"
    assert arguments.subtraction_path == \
           fixtures["data_path"]/"subtractions/id_with_spaces/reference"
    assert arguments.reads_path/"reads_1.fq.gz" in arguments.read_paths
    assert arguments.library_type == LibraryType.amplicon
    assert arguments.raw_path == fixtures["temp_path"]/"raw"


async def test_sub_fixtures_use_same_instance_of_analysis_args(fixtures):

    def use_fixtures(
            analysis_args: AnalysisArguments,
            analysis_path,
            analysis_document,
            sample,
            sample_path
    ):
        assert id(analysis_args.path) == id(analysis_path)
        assert id(analysis_args.analysis) == id(analysis_document)
        assert id(analysis_args.sample) == id(sample)
        assert id(analysis_args.sample_path) == id(sample_path)

    bound = await fixtures.bind(use_fixtures)
    bound()


async def test_correct_trimming_parameters(fixtures):
    params = await fixtures.instantiate(trimming_parameters)
    assert params == {
        "end_quality": 0,
        "mode": "pe",
        "max_error_rate": "0.1",
        "max_indel_rate": "0.03",
        "max_length": None,
        "mean_quality": 0,
        "min_length": 1
    }


@contextmanager
def init_reads_dir(path: Path):
    with context_directory(path) as read_dir:
        paths = utils.make_read_paths(read_dir, True)
        for path in paths:
            path.touch()

        yield paths


async def test_trimming_input_paths(fixtures):
    sample_path = await fixtures.get_or_instantiate("sample_path")
    shutil.copyfile(Path(__file__).parent/"large.fq.gz", sample_path/"reads_1.fq.gz")

    input_paths = await fixtures.instantiate(trimming_input_paths)

    assert input_paths[0].exists()


async def test_correct_trimming_output(fixtures):
    trimmed_read_path, _ = await fixtures.instantiate(trimming_output)

    files = list(trimmed_read_path.glob("*"))
    filenames = [p.name for p in files]

    assert "reads-trimmed.fastq.gz" in filenames
    assert "reads-trimmed.log" in filenames

    output = trimmed_read_path/"reads-trimmed.fastq.gz"
    expected = Path(__file__).parent/"large_trimmed.fq.gz"

    print(os.stat(output))
    print(os.stat(expected))

    assert filecmp.cmp(output, expected)


async def test_parsed_fastqc(fixtures):
    path = await fixtures.instantiate(trimming_output_path)
    fixtures["trimming_output"] = path, "TEST"

    shutil.copyfile(Path(__file__).parent/"large_trimmed.fq.gz", path/"reads-trimmed.fastq.gz")
    (path/"reads-trimmed.log").touch()

    fastqc = await fixtures.instantiate(parsed_fastqc)
    assert fastqc == fastqc_out.expected_output




