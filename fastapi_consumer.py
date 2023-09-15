import datetime
import logging
import os
import subprocess
from fastapi import Body, FastAPI
from fastapi.responses import FileResponse
import pika
import json
import uvicorn
from config import load_config
import os, sys
import yaml


config = load_config()

app = FastAPI()


def load_from_json(filename: str):
    """Load the data from the JSON file."""
    try:
        with open(filename, "r") as file:
            data = json.load(file)
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        # If the file does not exist or there's an error in reading it,
        # return an empty dictionary or other default value
        return {}


def consume_last_message_from_rabbitmq(json_backup_filename=str, queue=str):
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()

    # Fetch the message without auto acknowledgment
    method_frame, header_frame, body = channel.basic_get(queue=queue, auto_ack=False)

    if method_frame:
        # Extract the timestamp from the header frame
        if header_frame.timestamp:
            timestamp = header_frame.timestamp
            human_readable_timestamp = datetime.datetime.fromtimestamp(
                timestamp / 1000.0
            ).strftime("%Y-%m-%d %H:%M:%S")

        else:
            timestamp = None
        # Convert timestamp to human-readable format if necessary

        # # Acknowledge the message after processing
        # channel.basic_ack(delivery_tag=method_frame.delivery_tag)
        connection.close()
        data = json.loads(body.decode("utf-8"))
        if data == {} and os.path.exists(json_backup_filename):
            print("RabbitMQ queue NOT empty but message is")
            print("Loading from JSON file...")
            data_json = load_from_json(filename=json_backup_filename)
            file_timestamp = os.path.getmtime(json_backup_filename)
            file_timestamp = datetime.datetime.fromtimestamp(file_timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            return data_json, file_timestamp
        else:
            print("RabbitMQ queue NOT empty and message is NOT empty")
            return data, human_readable_timestamp

    else:
        if os.path.exists(json_backup_filename):
            connection.close()
            print("No message available, RabbitMQ queue is empty")
            print("Loading from JSON file...")
            data_json = load_from_json(filename=json_backup_filename)
            file_timestamp = os.path.getmtime(json_backup_filename)
            file_timestamp = datetime.datetime.fromtimestamp(file_timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            return data_json, file_timestamp
        else:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return {"workflows": []}, current_time


@app.get("/get-progress")
async def get_progress():
    data, timestamp = consume_last_message_from_rabbitmq(
        json_backup_filename=config["panoptes"]["json_status_backup"],
        queue=config["panoptes"]["rabbitmq"]["queue"],
    )

    print(data, timestamp)
    if data == {}:
        data = {"workflows": []}
    return data, timestamp


@app.get("/get-data")
def get_data():
    data, timestamp = consume_last_message_from_rabbitmq(
        json_backup_filename=config["data"]["json_data_backup"],
        queue=config["data"]["rabbitmq"]["queue"],
    )
    return data, timestamp


def run_second_command(
    cmd, profile_slurm, data_location, date_folder, working_directory="."
):
    """Run the second command and write the output to a log file."""

    print("\nThe output is as expected.")
    print("Running command: %s", " ".join(cmd))

    os.makedirs("watchdog/logs/per-run", exist_ok=True)

    # Get the current date and time
    now = datetime.datetime.now()

    # Convert it to a string
    current_time = now.strftime("%Y%m%d%H%M%S")

    with open(f"test.log", "w") as f:
        process2 = subprocess.Popen(
            cmd,
            # cmd + profile_slurm,
            stdout=f,
            stderr=f,
            universal_newlines=True,
            cwd=working_directory,  # Change working directory
            env=my_env,
        )
        process2.wait()

        print("Return code: %s", process2.returncode)

    # Change the permissions of the new directory
    # subprocess.run(["chmod", "-R", "777", f"{data_location}/{date_folder}"])


def execute_command(
    cmd,
    profile_dry_run,
    profile_slurm,
    dry_run_options,
    wms_monitor_args,
    data_location,
    date_folder,
    working_directory=".",
):
    # def execute_command(self, directory_path, prefix, working_directory="."):
    """Execute the command."""

    # Change directory and run the snakemake command
    # date_folder = directory_path.split("/")[-1]

    print("Running command: %s", " ".join(cmd + profile_dry_run + dry_run_options))

    # process = subprocess.Popen(
    #     # cmd + profile_dry_run + dry_run_options,
    #     cmd + dry_run_options,
    #     stdout=subprocess.PIPE,
    #     stderr=subprocess.STDOUT,
    #     universal_newlines=True,
    #     cwd=working_directory,  # Change working directory
    # )

    my_env = os.environ.copy()
    my_env[
        "PATH"
    ] = f"/Users/tweber/miniconda3/envs/snakemake_latest/bin:{my_env['PATH']}"

    print(my_env)
    print(working_directory)
    with open(f"test.log", "w") as f:
        process = subprocess.Popen(
            cmd + wms_monitor_args,
            # cmd + profile_slurm,
            stdout=f,
            stderr=f,
            universal_newlines=True,
            cwd=working_directory,  # Change working directory
            env=my_env,
        )
        print(cmd + wms_monitor_args)
        print(" ".join(cmd + wms_monitor_args))
        print(process)
        print(process.stdout)
        print(process.stderr)
        process.wait()

    # Variable to store the penultimate line
    penultimate_line = ""

    # Read the output line by line in real-time
    # for line in iter(process.stdout.readline, ""):
    #     print(line.strip())  # log line in real-time
    #     if line.strip():  # If line is not blank
    #         penultimate_line = line.strip()

    # Wait for the subprocess to finish
    # process.wait()
    print("Return code: %s", process.returncode)

    # Check the penultimate line
    # if str(process.returncode) == str(0):
    #     # self.run_second_command(cmd, profile_slurm, data_location, date_folder)
    #     run_second_command(
    #         cmd + wms_monitor_args, profile_slurm, data_location, date_folder
    #     )
    # else:
    #     print("\nThe output is not as expected.")


@app.post("/trigger-snakemake/{run_id}")
def trigger_snakemake(run_id: str, snake_args: dict = Body(...)):
    print(run_id)

    # data_location = "/scratch/tweber/DATA/MC_DATA/STOCKS"
    # publishdir_location = "/g/korbel/WORKFLOW_RESULTS"
    profile_slurm = ["--profile", "workflow/snakemake_profiles/HPC/slurm_EMBL/"]
    profile_dry_run = ["--profile", "workflow/snakemake_profiles/local/conda/"]
    dry_run_options = ["-c", "1", "-n", "-q"]
    snakemake_binary = "/g/korbel2/weber/miniconda3/envs/snakemake_latest/bin/snakemake"
    snakemake_binary = "/Users/tweber/miniconda3/envs/snakemake_latest/bin/snakemake"
    wms_monitor_options = config["panoptes"]["url"]
    wms_monitor_renaming_option = f"name={run_id}"
    sample_name = f"{run_id}".split("--")[2]

    # Append the snake_args to cmd
    snake_args_list = list()
    for key, value in snake_args.items():
        if value is not None:
            snake_args_list.append(f"{key}={value}")

    # cmd = [
    #     f"{snakemake_binary}",
    #     "--nolock",
    #     "--rerun-triggers mtime",
    #     "--config",
    #     "genecore=True",
    #     "split_qc_plot=False",
    #     # f"publishdir={publishdir_location}",
    #     # "email=thomas.weber@embl.de",
    #     f"data_location={data_location}",
    #     f'samples_to_process="[{sample_name}]"',
    # ]

    cmd = [
        f"{snakemake_binary}",
        "--nolock",
        # "--rerun-triggers mtime",
        "--forceall",
        "--cores",
        "1",
        "--config",
        # "blacklisting=False",
        # "split_qc_plot=False",
        # # f"publishdir={publishdir_location}",
        # # "email=thomas.weber@embl.de",
        # f"data_location={data_location}",
        # f'samples_to_process="[{sample_name}]"',
    ]

    wms_monitor_args = [
        "--wms-monitor",
        f"{wms_monitor_options}",
        "--wms-monitor-arg",
        f"{wms_monitor_renaming_option}",
    ]

    cmd = cmd + snake_args_list

    # execute_command(directory_path, prefixes.pop())
    execute_command(
        cmd=cmd,
        profile_dry_run=profile_dry_run,
        profile_slurm=profile_slurm,
        dry_run_options=dry_run_options,
        wms_monitor_args=wms_monitor_args,
        data_location="",
        date_folder="",
        working_directory="/Users/tweber/Gits/snakemake_logs_dev",
    )


@app.get("/reports/{run}--{sample}/{pipeline}/report.html")
def serve_report(pipeline: str, run: str, sample: str):
    data_folder = config["data"]["data_folder"]
    file_path = f"{data_folder}/{run}/{sample}/{pipeline}_REPORT/report.html"
    print(file_path)

    # Check if the file exists
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="text/html")
    else:
        return {"error": "File not found!"}

