from virtool_workflow import fixture, Workflow

__fixtures__ = [
    ("virtool_workflow.config.fixtures", "data_path", "work_path"),
    "virtool_workflow.execution.run_in_executor"
]


@fixture
def fixture_a() -> str:
    return "a"


@fixture
def fixture_b(fixture_a: str) -> str:
    return f"{fixture_a}b"


@fixture
async def fixture_c() -> str:
    return "c"


wf = Workflow()


@wf.startup
def start(fixture_a, fixture_b, fixture_c, results):
    results["fixture_a"] = fixture_a
    results["fixture_b"] = fixture_b
    results["fixture_c"] = fixture_c

    return "In file fixtures are correctly loaded"


@wf.step
def step(data_path, work_path, thread_pool_executor, run_in_executor, results):
    results["data_path"] = data_path
    results["work_path"] = work_path
    results["thread_pool_executor"] = thread_pool_executor
    results["run_in_executor"] = run_in_executor

    return "__fixtures__ loaded correctly"
