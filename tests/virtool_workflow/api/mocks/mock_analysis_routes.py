from pathlib import Path

from aiohttp import web, ContentTypeError

from tests.virtool_workflow.api.mocks.utils import read_file_from_request

mock_routes = web.RouteTableDef()


@mock_routes.get("/api/analyses/{analysis_id}")
async def get_analysis(request):
    id_ = request.match_info["analysis_id"]

    if id_ != "test_analysis":
        return web.json_response({
            "message": "Not Found"
        }, status=404)

    return web.json_response({
        "id": "test_analysis",
        "created_at": "2017-10-03T21:35:54.813000Z",
        "job": {
            "id": "test_job"
        },
        "files": [
            {
                "analysis": "test_analysis",
                "description": None,
                "format": "fasta",
                "id": 1,
                "name": "results.fa",
                "name_on_disk": "1-results.fa",
                "size": 20466,
                "uploaded_at": "2017-10-03T21:35:54.813000Z"
            }
        ],
        "workflow": "pathoscope_bowtie",
        "sample": {
            "id": "kigvhuql",
            "name": "Test 1"
        },
        "index": {
            "id": "qldihken",
            "version": 0
        },
        "user": {
            "id": "igboyes"
        },
        "subtractions": [
            {
                "id": "yhxoynb0",
                "name": "Arabidopsis Thaliana"
            }
        ],
        "ready": False
    }, status=200)


@mock_routes.post("/api/analyses/{analysis_id}/files")
async def upload_file(request):
    name = request.query.get("name")
    format = request.query.get("format")

    return web.json_response(await read_file_from_request(request, name, format), status=201)


@mock_routes.get("/api/analyses/{analysis_id}/files/{file_id}")
async def download(request):
    file_id = request.match_info["file_id"]
    analysis_id = request.match_info["analysis_id"]

    if file_id == "0" and analysis_id == TEST_ANALYSIS_ID:
        test_file = Path("test.txt")
        test_file.write_text("TEST")
        response = web.FileResponse(test_file)

        return response

    return web.json_response({
        "message": "Not Found"
    }, status=404)


@mock_routes.delete("/api/analyses/{analysis_id}")
async def delete(request):
    analysis_id = request.match_info["analysis_id"]

    if analysis_id != TEST_ANALYSIS_ID:
        return web.json_response({
            "message": "Not Found"
        }, status=404)

    return web.Response(status=204)


@mock_routes.patch("/api/analyses/{analysis_id}")
async def upload_result(request):
    analysis_id = request.match_info["analysis_id"]
    if analysis_id != TEST_ANALYSIS_ID:
        return web.json_response({
            "message": "Not Found"
        }, status=404)

    try:
        req_json = await request.json()
        results = req_json["results"]
    except (ContentTypeError, KeyError):
        return web.json_response({
            "message": "Invalid JSON body."
        }, status=422)

    if "ready" in TEST_ANALYSIS and TEST_ANALYSIS["ready"] is True:
        return web.json_response({
            "message": "There is already a result."
        }, status=409)

    TEST_ANALYSIS.update(
        {
            "results": results,
            "ready": True
        }
    )

    return web.json_response(TEST_ANALYSIS, status=200)


TEST_ANALYSIS_ID = "test_analysis"
TEST_ANALYSIS = {
    "id": TEST_ANALYSIS_ID,
    "created_at": "2017-10-03T21:35:54.813000Z",
    "job": {
        "id": "test_job"
    },
    "files": [
        {
            "analysis": "test_analysis",
            "description": None,
            "format": "fasta",
            "id": 1,
            "name": "results.fa",
            "name_on_disk": "1-results.fa",
            "size": 20466,
            "uploaded_at": "2017-10-03T21:35:54.813000Z"
        }
    ],
    "workflow": "pathoscope_bowtie",
    "sample": {
        "id": "kigvhuql",
        "name": "Test 1"
    },
    "index": {
        "id": "qldihken",
        "version": 0
    },
    "user": {
        "id": "igboyes"
    },
    "subtractions": [
        {
            "id": "yhxoynb0",
            "name": "Arabidopsis Thaliana"
        }
    ],
    "ready": False
}
