import json
from dataclasses import dataclass
from pathlib import Path
from shutil import copytree
from typing import Dict, List, Tuple, Optional, Any

import aiofiles
from virtool_core.utils import decompress_file

from virtool_workflow import fixture
from virtool_workflow.abc import AbstractDatabase
from virtool_workflow.execution.run_in_executor import FunctionExecutor
from virtool_workflow.execution.run_subprocess import RunSubprocess


@dataclass
class Reference:
    """Represents a Virtool reference"""

    id: str
    data_type: str
    name: str


class Index:
    """Represents a reference index assigned to the workflow run.

    :param index_id: the unique ID for the index
    :param path: the path at which the workflow index data will be stored
    :param: reference: the index's parent reference
    :param: run_in_executor: a function that calls functions in a :class:`ThreadPoolExecutor()`
    :param: run_subprocess: a function that runs a command as a subprocess

    """
    def __init__(
        self,
        index_id: str,
        path: Path,
        reference: Reference,
        run_in_executor: FunctionExecutor,
        run_subprocess: RunSubprocess,
    ):
        self.id = index_id
        self.path = path
        self.reference = reference
        self._run_in_executor = run_in_executor
        self._run_subprocess = run_subprocess

        self.bowtie_path: Path = self.path / "reference"
        self.fasta_path: Path = self.path / "ref.fa"
        self.compressed_json_path: Path = self.path / "reference.json.gz"
        self.json_path: Path = self.path / "reference.json"

        self._sequence_lengths: Optional[Dict[str, int]] = None
        self._sequence_otu_map: Optional[Dict[str, str]] = None

    async def decompress_json(self, processes: int):
        """
        Decompress the gzipped JSON file stored in the reference index directory. This data will be used to generate
        isolate indexes if required.

        Populate the ``sequence_otu_map`` attribute.

        :param processes: the number processes available for decompression

        """
        if self.json_path.is_file():
            raise FileExistsError("Index JSON file has already been decompressed")

        await self._run_in_executor(
            decompress_file, self.compressed_json_path, self.json_path, processes
        )

        async with aiofiles.open(self.json_path) as f:
            data = json.loads(await f.read())

        sequence_lengths = dict()
        sequence_otu_map = dict()

        for otu in data["otus"]:
            for isolate in otu["isolates"]:
                for sequence in isolate["sequences"]:
                    sequence_id = sequence["_id"]

                    sequence_otu_map[sequence_id] = otu["_id"]
                    sequence_lengths[sequence_id] = len(sequence["sequence"])

        self._sequence_lengths = sequence_lengths
        self._sequence_otu_map = sequence_otu_map

    def get_otu_id_by_sequence_id(self, sequence_id: str) -> str:
        """
        Return the OTU ID associated with the given ``sequence_id``.

        :param sequence_id: the sequence ID
        :return: the matching OTU ID

        """
        try:
            return self._sequence_otu_map[sequence_id]
        except KeyError:
            raise ValueError("The sequence_id does not exist in the index")

    def get_sequence_length(self, sequence_id: str) -> int:
        """
        Get the sequence length for the given ``sequence_id``.

        :param sequence_id: the sequence ID
        :return: the length of the sequence

        """
        try:
            return self._sequence_lengths[sequence_id]
        except KeyError:
            raise ValueError("The sequence_id does not exist in the index")

    async def write_isolate_fasta(
        self, otu_ids: List[str], path: Path
    ) -> Dict[str, int]:
        """
        Generate a FASTA file for all of the isolates of the OTUs specified by ``otu_ids``.

        :param otu_ids: the list of OTU IDs for which to generate and index
        :param path: the path to the reference index directory
        :return: a dictionary of the lengths of all sequences keyed by their IDS

        """
        unique_otu_ids = set(otu_ids)

        async with aiofiles.open(self.json_path) as f:
            data = json.loads(await f.read())

        otus = [otu for otu in data["otus"] if otu["_id"] in unique_otu_ids]

        lengths = dict()
        sequence_otu_dict = dict()

        async with aiofiles.open(path, "w") as f:
            for otu in otus:
                for isolate in otu["isolates"]:
                    for sequence in isolate["sequences"]:
                        await f.write(f">{sequence['_id']}\n{sequence['sequence']}\n")
                        lengths[sequence["_id"]] = len(sequence["sequence"])

        return lengths

    async def build_isolate_index(
        self, otu_ids: List[str], path: Path, processes: int
    ) -> Tuple[Path, Dict[str, int]]:
        """
        Generate a FASTA file and Bowtie2 index for all of the isolates of the OTUs specified by ``otu_ids``.

        :param otu_ids: the list of OTU IDs for which to generate and index
        :param path: the path to the reference index directory
        :param processes: how many processes are available for external program calls
        :return: a tuple containing the path to the Bowtie2 index, FASTA files, and a dictionary of the lengths of all sequences keyed by their IDS

        """
        fasta_path = Path(f"{path}.fa")

        lengths = await self.write_isolate_fasta(otu_ids, fasta_path)

        command = [
            "bowtie2-build",
            "--threads",
            str(processes),
            str(fasta_path),
            str(path),
        ]

        await self._run_subprocess(command)

        return fasta_path, lengths


@fixture
async def indexes(
    database: AbstractDatabase,
    job_args: Dict[str, Any],
    data_path: Path,
    temp_path: Path,
    run_in_executor: FunctionExecutor,
    run_subprocess: RunSubprocess,
) -> List[Index]:
    """
    A workflow fixture that lists all reference indexes required for the workflow as :class:`.Index` objects.

    """
    index_document = await database.fetch_document_by_id(
        job_args["index_id"], "indexes"
    )

    ref_document = await database.fetch_document_by_id(
        index_document["reference"]["id"], "references"
    )

    src_path = data_path / "references" / ref_document["_id"] / job_args["index_id"]
    dst_path = temp_path / "indexes" / job_args["index_id"]

    await run_in_executor(copytree, src_path, dst_path)

    reference = Reference(
        ref_document["_id"],
        ref_document["data_type"],
        ref_document["name"],
    )

    index = Index(
        job_args["index_id"], dst_path, reference, run_in_executor, run_subprocess
    )

    await index.decompress_json(job_args["proc"])

    return [index]