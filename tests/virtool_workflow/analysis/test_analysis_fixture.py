from functools import wraps
from pathlib import Path

import aiohttp
from virtool_workflow import hooks
from virtool_workflow.analysis.analysis import Analysis
from virtool_workflow.api.analysis import AnalysisProvider


def _count_calls(func):
    @wraps(func)
    async def _counting(*args, **kwargs):
        _counting.call_count += 1
        return await func(*args, **kwargs)

    _counting.call_count = 0

    return _counting


async def test_analysis_fixture(runtime, http: aiohttp.ClientSession, jobs_api_url: str):
    provider = runtime["analysis_provider"] = AnalysisProvider(runtime["job"].args["analysis_id"], http, jobs_api_url)

    provider.upload = _count_calls(provider.upload)

    analysis = await runtime.get_or_instantiate("analysis")

    assert isinstance(analysis, Analysis)

    test_file = Path("test.json")

    test_file.write_text("{'foo':'bar'}")

    try:
        analysis.upload(test_file, "json")

        await hooks.on_success.trigger(runtime)

        assert provider.upload.call_count == 1
    finally:
        test_file.unlink()
