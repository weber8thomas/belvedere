import git
import time
import os

repo_url = "https://github.com/snakemake-workflows/dna-seq-varlociraptor"
# repo_url = "https://github.com/weber8thomas/smk-dummy-repo"
# repo_dir = "/g/korbel2/weber/TMP/repos/smk-dummy-repo"
repos_dir = "/scratch/tweber/TMP"
repo_dir = f"{repos_dir}/{repo_url.split('/')[-1].replace('.git', '')}"

# check if the repo has already been cloned
if not os.path.exists(repo_dir):
    print("Cloning")
    # clone the repo if it has not been cloned yet
    git.Repo.clone_from(repo_url, repo_dir)

# if the repo has already been cloned, open it using GitPython
repo = git.Repo(repo_dir)
print(repo)

# repo = git.Repo(repo_dir)
# latest_commit = repo.head.commit
# print(f"Latest commit: {latest_commit}")
tags = repo.tags
print(tags)
# time.sleep(60)  # wait for 60 seconds before checking again
