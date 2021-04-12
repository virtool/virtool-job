import os
import tempfile
from pathlib import Path
from subprocess import call

import click

from .utils import DONE, bcolors, clone, color, docker_build

HERE = Path(__file__).parent

JOBS_API_DOCKERFILE = HERE / "api-server-Dockerfile"
WORKFLOW_DOCKER_FILE = HERE / "latest-workflow-local-Dockerfile"
SPECIFIC_WORKFLOW_DOCKERFILE = HERE / "specific-workflow-Dockerfile"
INTEGRATION_WORKFLOW_DOCKER_FILE = HERE / "workflow/Dockerfile"

SUB_WORKFLOWS_PATH = HERE / "workflow/integration_test_workflows"


@click.group()
def cli():
    ...


@cli.group()
def run():
    ...


for sub_workflow_path in SUB_WORKFLOWS_PATH.glob(r"*.py"):
    name = sub_workflow_path.with_suffix("").name
    if name.startswith("_"):
        continue

    @run.command(name, help=f"Run the {name} test workflow.")
    @click.pass_context
    def __cmd(ctx):
        os.environ["VT_WORKFLOW_FILE"] = str(sub_workflow_path.relative_to(HERE/"workflow"))
        ctx.invoke(up)

    __cmd.__name__ = __cmd.__qualname__ = name


@cli.command()
@click.pass_context
def up(ctx):
    """Run the integration tests using docker-compose"""
    call(
        "docker-compose up --exit-code-from=integration_test_workflow",
        shell=True,
        cwd=HERE,
        env=os.environ,
    )


@cli.group()
def build():
    """Build the required docker images with the latest version of the code."""
    ...


@click.option(
    "--path",
    default=HERE.parent.parent,
    type=click.Path(),
    help="The path to a local clone of the virtool-workflow git repository.",
)
@click.option(
    "--remote", default=None, help="The virtool-workflow git repository to pull from."
)
@build.command()
def workflow(path, remote):
    """Build the `virtool/workflow` image."""
    tag = "virtool/workflow"
    if remote is not None:
        tempd = tempfile.mkdtemp()
        print(color(bcolors.OKBLUE, f"Created temporary directory {tempd}..."))
        print(color(bcolors.OKBLUE, f"Cloning {remote}...\n"))
        clone(remote, cwd=tempd)
        context = Path(tempd) / "virtool-workflow"
    else:
        context = path

    print(color(bcolors.OKBLUE, f"\nBuilding `{color(bcolors.OKGREEN, tag)}`...\n"))
    docker_build(
        dockerfile=WORKFLOW_DOCKER_FILE, context=context, tag=tag,
    )


@build.command()
def integration():
    """Build the `virtool/integration_test_workflow` image."""
    tag = "virtool/integration_test_workflow"
    print(color(bcolors.OKBLUE, f"\nBuilding `{color(bcolors.OKGREEN, tag)}`...\n"))
    docker_build(
        dockerfile=INTEGRATION_WORKFLOW_DOCKER_FILE, context=HERE / "workflow", tag=tag,
    )
    print(DONE)


@click.option(
    "--remote",
    default="https://github.com/virtool/virtool@release/5.0.0",
    help="The virtool git repository to pull from.",
)
@click.option(
    "--path",
    default=None,
    help="The path to a local clone of the virtool git repository.",
)
@build.command()
def jobs_api(path, remote):
    """Build the `virtool/jobs-api` image."""
    tag = "virtool/jobs-api"
    if path is None:
        tempd = tempfile.mkdtemp()
        print(color(bcolors.OKBLUE, f"Created temporary directory {tempd}..."))
        print(color(bcolors.OKBLUE, f"Cloning {remote}...\n"))
        clone(remote, cwd=tempd)

        context = Path(tempd) / "virtool"
    else:
        context = path

    print(color(bcolors.OKBLUE, f"\nBuilding `{color(bcolors.OKGREEN, tag)}`...\n"))

    docker_build(
        dockerfile=JOBS_API_DOCKERFILE, context=context, tag=tag,
    )

    print(DONE)


@click.option(
    "--virtool-remote",
    default="https://github.com/virtool/virtool@release/5.0.0",
    help="The virtool git repository to pull from.",
)
@click.option(
    "--virtool-path",
    default=None,
    help="The path to a local clone of the virtool git repository.",
)
@click.option(
    "--virtool-workflow-path",
    default="..",
    type=click.Path(),
    help="The path to a local clone of the virtool-workflow git repository.",
)
@click.option(
    "--virtool-workflow-remote",
    default=None,
    help="The virtool-workflow git repository to pull from.",
)
@build.command()
@click.pass_context
def all(
    ctx, virtool_remote, virtool_path, virtool_workflow_remote, virtool_workflow_path
):
    """Build all of the required images."""
    ctx.invoke(workflow, remote=virtool_workflow_remote, path=virtool_workflow_path)
    ctx.invoke(integration)
    ctx.invoke(jobs_api, remote=virtool_remote, path=virtool_path)
