from fastapi import FastAPI, Query
import os, sys
import subprocess
from pydantic import BaseModel
from typing import Literal
import collections
import json
import yaml
import pandas as pd
from pprint import pprint
import psutil, time, hashlib
from datetime import datetime
import git


app = FastAPI(title="Belvedere")

# WARNING: CONFIG
belvedere_database = "example.db"
local_dir = "/scratch/tweber/dev/belvedere/"
folder_repos = "repos"
folder_runs = "runs"
local_dir = f"{local_dir}/" if local_dir.endswith("/") is False else local_dir


def clone_or_update_repo(repo_url, clonedir, engine="snakemake"):
    if not os.path.exists(repo_dir):
        print("Cloning")
        # clone the repo if it has not been cloned yet
        git.Repo.clone_from(repo_url, repo_dir)
    repo = git.Repo(repo_dir)
    print(repo)


import sqlite3


@app.post("/add-repo/{repo_url:path}", tags=["workflows"])
async def add_repository(repo_url: str, engine: str = Query("Snakemake", enum=["CWL", "nextflow", "snakemake"])):
    repo_name = repo_url.split("/")[-1]
    # local_dir_tmp = local_dir + f"{folder_repos}/{engine}/{repo_name}"
    # print(local_dir_tmp)
    # status = clone_or_update_repo(repo_url, local_dir_tmp, engine)
    json_data = {"url": repo_url, "engine": engine, "creation_date": datetime.today().strftime("%Y-%m-%d %H:%M:%S")}
    print(json_data)

    # Connect to the SQLite database
    conn = sqlite3.connect(belvedere_database)
    c = conn.cursor()

    # Create a table if it does not exist
    c.execute(
        """CREATE TABLE IF NOT EXISTS repositories
                 (url text, engine text, creation_date text)"""
    )

    # Check if the repo is already in the table
    c.execute("SELECT * FROM repositories WHERE url = ?", (repo_url,))
    row = c.fetchone()
    if row is not None:
        conn.close()
        return {"message": f"The repository {repo_url} has already been added to the table."}

    # Insert data into the table
    c.execute("INSERT INTO repositories VALUES (?, ?, ?)", (repo_url, engine, json_data["creation_date"]))

    # Commit the transaction and close the connection
    conn.commit()
    conn.close()

    # with open(f"{local_dir_tmp}/.wf_medata.json", "w", encoding="utf-8") as f:
    #     json.dump(json_data, f, ensure_ascii=False, indent=4)
    return json_data
    # return f"Cloned or updated repository {repo_url} to {local_dir}"


def list_folders(path, key_folder):
    if os.path.isdir(f"{path}/{key_folder}"):
        if key_folder == folder_runs:
            d = collections.defaultdict(dict)
        else:
            d = collections.defaultdict(list)

        for engine in os.listdir(f"{path}/{key_folder}"):
            if key_folder == folder_runs:
                if engine not in d:
                    d[engine] = collections.defaultdict(list)
            for repo in os.listdir(f"{path}/{key_folder}/{engine}"):
                if key_folder is folder_repos:
                    d[engine].append(repo)
                # print(f"{path}/{key_folder}/{engine}/{repo}")
                elif key_folder == folder_runs:
                    for run in os.listdir(f"{path}/{key_folder}/{engine}/{repo}"):
                        # print(f"{path}/{key_folder}/{engine}/{repo}/{run}")
                        d[engine][repo].append(run)

        return d


@app.get("/list-wfs", tags=["workflows"])
async def list_wfs():

    # Connect to the SQLite database
    conn = sqlite3.connect(belvedere_database)
    c = conn.cursor()

    # Retrieve the repository URLs and engines from the table
    c.execute("SELECT url, engine FROM repositories")
    rows = c.fetchall()

    # Close the connection
    conn.close()

    # Convert the rows to a dictionary
    d = {row[1]: [] for row in rows}
    for row in rows:
        d[row[1]].append(row[0])

    return d
    # return list_folders(path=local_dir, key_folder=folder_repos)
    # return f"Cloned or updated repository {repo_url} to {local_dir}"


def local_list_wfs():
    d_wfs = list_folders(path=local_dir, key_folder=folder_repos)
    if d_wfs:
        list_wfs = [f"{engine}/{wf}" for engine, wfs in d_wfs.items() for wf in wfs]
    else:
        list_wfs = [""]
    return list_wfs


@app.get("/list-wf-versions", tags=["workflows"])
async def list_wf_versions(repo: str = Query(local_list_wfs()[0], enum=(local_list_wfs()))):
    metadata_wf = json.load(open(f"{local_dir}/{folder_repos}/{repo}/.wf_medata.json", "r"))

    # pprint(metadata_wf)
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


@app.get("/list-wf-runs", tags=["runs"])
async def list_runs():
    return list_folders(path=local_dir, key_folder=folder_runs)


def local_list_runs():
    d_wfs = list_folders(path=local_dir, key_folder=folder_runs)
    if d_wfs:
        list_wfs = [f"{engine}/{wf}/{run}" for engine, wfs in d_wfs.items() for wf in wfs for run in d_wfs[engine][wf]]
    else:
        list_wfs = [""]
    return list_wfs


@app.get("/explore-run", tags=["runs"])
async def explore_run(run: str = Query(local_list_runs()[0], enum=(local_list_runs()))):
    runs = list_folders(path=local_dir, key_folder=folder_runs)
    return runs


@app.post("/trigger-run", tags=["runs"])
async def trigger_workflow_run(
    repo: str = Query(local_list_wfs()[-1], enum=(local_list_wfs())), cmd: str = "", data: str = "/scratch/tweber/DATA/MC_DATA/TEST_DATA"
):
    metadata_wf = json.load(open(f"{local_dir}/{folder_repos}/{repo}/.wf_medata.json", "r"))

    workflow_url = metadata_wf["url"]
    workflow_engine = metadata_wf["engine"]
    date = datetime.today().strftime("%Y-%m-%d")
    data_folder = data
    concatenated_string = workflow_url + workflow_engine + date + data_folder
    print(concatenated_string)

    hashed_value = hashlib.sha256(concatenated_string.encode()).hexdigest()
    print(hashed_value)

    repo_name = repo.split("/")[-1]
    print(repo_name)
    print(cmd)
    run_dir = f"{local_dir}/{folder_runs}/{repo}/{hashed_value}"
    print(run_dir)

    clone_or_update_repo(repo_url=metadata_wf["url"], clonedir=run_dir, engine=metadata_wf["engine"])
    # # subprocess.call(f"cd {local_dir}/{folder_repos}/{repo}", shell=True)
    # os.chdir(run_dir)
    # p = subprocess.Popen(f"pwd", shell=True, stdout=subprocess.PIPE).communicate()[0].decode("utf-8").split("\n")
    # print(p)

    # process = subprocess.Popen(cmd, shell=True)
    # pid = process.pid
    # print("PID of the subprocess:", pid)

    # # Get the process object using the PID
    # process = psutil.Process(pid)
    # i = 0
    # while i < 40:

    #     # Check the status of the process
    #     status = process.status()
    #     print("Status of the subprocess:", status)
    #     time.sleep(1)
    #     i += 1

    # os.chdir(f"{local_dir}/{folder_repos}/{repo}")

    # # return f"Cloned or updated repository {repo_url} to {local_dir}"
