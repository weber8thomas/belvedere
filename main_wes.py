from typing import List
from fastapi import FastAPI, Query
from pydantic import BaseModel

app = FastAPI()


class Workflow(BaseModel):
    workflow_name: str
    workflow_url: str
    workflow_type: str
    workflow_type_version: List[str]


@app.get("/executable-workflows", response_model=List[Workflow])
async def get_executable_workflows():
    workflows = [
        Workflow(
            workflow_name="example_workflow",
            workflow_url="https://example.com/workflow.cwl",
            workflow_type="CWL",
            workflow_type_version=["v1.0"],
        )
    ]
    return workflows


class RunStatus(BaseModel):
    # define the properties of RunStatus here
    pass


class RunListResponse(BaseModel):
    runs: List[RunStatus]
    next_page_token: str


class RunRequest(BaseModel):
    # define the properties of RunRequest here
    pass


class RunId(BaseModel):
    id: str


class ErrorResponse(BaseModel):
    # define the properties of ErrorResponse here
    pass


@app.get("/runs")
async def list_runs(
    page_size: int = Query(
        None,
        description="The preferred number of workflow runs to return in a page. If not provided, the implementation should use a default page size. The implementation must not return more items than `page_size`, but it may return fewer. Clients should not assume that all items have been returned if fewer than `page_size` items are returned. The value of `next_page_token` indicates the availability of additional pages in the response.",
    ),
    page_token: str = Query(
        None, description="Token to use to indicate where to start getting results. If unspecified, return the first page of results."
    ),
):
    """
    List the workflow runs.

    This list should be provided in a stable ordering. (The actual order is implementation-dependent.)
    When paging through the list, the client should not make assumptions about live updates but should assume the list's contents reflect the workflow list when the first page is requested.
    To monitor a specific workflow run, use `GetRunStatus` or `GetRunLog`.
    """
    # implementation of list_runs endpoint
    