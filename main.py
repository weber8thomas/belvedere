from fastapi import FastAPI, Query
import os, sys
import subprocess
from pydantic import BaseModel
from typing import Literal
import collections
import json
import yaml

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/toto")
async def root():
    return {"message": "Hello toto"}


working_dir = "/g/korbel2/weber/workspace/flask-dev"
local_dir = "TEST/repos/"
local_dir = f"{local_dir}/" if local_dir.endswith("/") is False else local_dir


def clone_or_update_repo(repo_url, clonedir, tag="", engine="snakemake"):

    clone_list = ["git", "clone", repo_url, clonedir]
    if tag:
        tag_list = ["--branch", tag]
        clone_list += tag_list
    if not os.path.exists(clonedir):
        # If the local directory doesn't exist, clone the repo
        subprocess.run(clone_list)
        return {"status": "clone", "directory": clonedir}
    else:
        # If the local directory already exists, pull the latest changes from the repo
        # subprocess.run(["git", "pull"], cwd=local_dir)
        return {"status": "pass", "directory": clonedir}


@app.post("/clone-repo/{repo_url:path}")
async def clone_repo(repo_url: str, tag: str = "", engine: str = Query("Snakemake", enum=["CWL", "nextflow", "snakemake"])):
    repo_name = repo_url.split("/")[-1]
    local_dir_tmp = local_dir + f"{engine}/{repo_name}"
    print(local_dir_tmp)
    tag = tag if tag else "master"
    status = clone_or_update_repo(repo_url, local_dir_tmp, tag, engine)
    json_data = {**{"url": repo_url, "tag": tag, "engine": engine}, **status}
    with open(f"{local_dir_tmp}/.wf_medata.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    return json_data
    # return f"Cloned or updated repository {repo_url} to {local_dir} with {tag}"


def list_folders(path):
    if os.path.isdir(path):
        d = collections.defaultdict(list)
        for engine in os.listdir(path):
            for repo in os.listdir(f"{path}/{engine}"):
                d[engine].append(repo)
                print(f"{path}/{engine}/{repo}")
        return d


@app.get("/list-wfs")
async def list_wfs(local_dir: str = local_dir):
    return list_folders(local_dir)
    # return f"Cloned or updated repository {repo_url} to {local_dir} with {tag}"


def local_list_wfs():
    d_wfs = list_folders(local_dir)
    # if d_wfs:
    list_wfs = [f"{engine}/{wf}" for engine, wfs in d_wfs.items() for wf in wfs]
    print(list_wfs)
    return list_wfs


@app.get("/list-wf-versions")
async def list_wf_versions(local_dir: str = local_dir, repo: str = Query(local_list_wfs()[0], enum=(local_list_wfs()))):
    metadata_wf = json.load(open(f"{local_dir}/{repo}/.wf_medata.json", "r"))
    from pprint import pprint

    pprint(metadata_wf)
    repo_url = metadata_wf["url"]
    res_tags = (
        subprocess.Popen(f"git ls-remote --tags {repo_url}", shell=True, stdout=subprocess.PIPE)
        .communicate()[0]
        .decode("utf-8")
        .split("\n")
    )
    res_tags = [{"Tag": e.split("\t")[1].replace("refs/tags/", ""), "Commit": e.split("\t")[0]} for e in res_tags[:-1]]
    metadata_wf["Tags"] = res_tags

    return [{"Workflow": repo, "Metadata": metadata_wf}]
    # return f"Cloned or updated repository {repo_url} to {local_dir} with {tag}"
