# Virtool Workflow Integration Tests

## Installation

The `virtool_integration` package can be installed by;

```shell script
pip install .
```

## Building the Docker Images



```shell script
./build.sh
```

The latest version of the `virtool_workflow` library is pulled from github and installed into the 
`virtool/workflow` image. This allows new features of `virtool_workflow` to be tested before they 
released to pypi.

The `virtool/integration_test_workflow` and `virtool/job-api` docker images are produced.

## Running the Tests

```shell script
./build.sh
docker-compose up
```

### Using a fork

The `build.sh` script accepts some options to allow use of forks.

```shell script
./build.sh --help
```

```text
    Build the docker images for the 'virtool_workflow' integration tests.

    Syntax: ./build.sh [--virtool-repo|--virtool-workflow-repo|--local-virtool-workflow|--local-virtool]
    Options:
    --virtool-repo             The URL of the virtool github repo (to use your fork).
    --virtool-branch           The name of the branch to pull from the virtool repo.
    --virtool-workflow-repo    The URL of the virtool-workflow github repo (to use your fork).
    --local-virtool-workflow   The path to the local virtool-workflow directory.
    --local-virtool            The path to the local virtool directory.
```

To use a specific branch of `virtool_workflow` you can give;

```shell script
./build.sh --virtool-workflow-repo pip install git+https://github.com/{username}/{repo_name}.git@{branch_name}
```

To use local files instead of pulling from github use;

```shell script
./build.sh --local-virtool "/path/to/virtool" --local-virtool-workflow "/path/to/local/virtool-workflow"
```