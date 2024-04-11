import datetime
import logging
import os
import subprocess
from fastapi import Body, FastAPI
from fastapi.responses import FileResponse
import pika
import json
from config import load_config
import os
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
    
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(config["rabbitmq_general_settings"]["hostname"])
    )
    channel = connection.channel()

    # Fetch the message without auto acknowledgment
    method_frame, header_frame, body = channel.basic_get(queue=queue, auto_ack=False)

    if method_frame:
        # Extract the timestamp from the header frame
        # if header_frame.timestamp:
        timestamp = header_frame.timestamp
        human_readable_timestamp = datetime.datetime.fromtimestamp(
            timestamp / 1000.0
        ).strftime("%Y-%m-%d %H:%M:%S")

        # else:
        #     timestamp = None
        # Convert timestamp to human-readable format if necessary

        # # Acknowledge the message after processing
        channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
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

    # print(data, timestamp)
    # if data == {}:
    #     data = {"workflows": []}
    # return data, timestamp
    # message_df = pd.read_json(StringIO(data), orient="records")
    # pd.options.display.max_rows = 999
    # pd.options.display.max_colwidth = 30
    # print(message_df)
    # print(timestamp)
    return data, timestamp


@app.get("/get-data")
def get_data():
    data, timestamp = consume_last_message_from_rabbitmq(
        json_backup_filename=config["data"]["json_data_backup"],
        queue=config["data"]["rabbitmq"]["queue"],
    )
    return data, timestamp


@app.post("/trigger-snakemake/{run_id}")
def trigger_snakemake(run_id: str, snake_args: dict = Body(...)):
    def execute_command(
        cmd,
        profile_dry_run,
        profile_slurm,
        dry_run_options,
        wms_monitor_args,
        data_location,
        date_folder,
        working_directory=".",
        report_location=".",
        pipeline=str,
        sample_name=str,
        publishdir_location=str,
    ):
        """Execute the command using dry-run to make sure the DAG is well computed"""

        print("Running command: %s", " ".join(cmd + profile_dry_run + dry_run_options))

        # Complete environment
        snakemake_binary_folder = "/".join(
            config["snakemake"]["binary"].split("/")[:-1]
        )
        my_env = os.environ.copy()
        my_env["PATH"] = f"{snakemake_binary_folder}:{my_env['PATH']}"

        print(
            f"{publishdir_location}/{date_folder}/{sample_name}/config/strandscape.json"
        )
        stranscape_json = json.load(
            open(
                f"{publishdir_location}/{date_folder}/{sample_name}/config/strandscape.json",
                "r",
            )
        )
        cell = stranscape_json["stored-selectedRows"][0]["cell"]

        # cmd = cmd[:-2] + [
        #     "--force",
        #     f"{data_location}/{date_folder}/{sample_name}/debug/mosaicatcher_fastqc/{cell}.1_fastqc.html",
        #     "--rerun-triggers",
        #     "mtime",
        # ]

        print(cmd + profile_dry_run + dry_run_options)
        print(" ".join(cmd + profile_dry_run + dry_run_options))

        # # Prepare process to perform dry run
        # process = subprocess.Popen(
        #     cmd + profile_dry_run + dry_run_options,
        #     # cmd + dry_run_options,
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.STDOUT,
        #     universal_newlines=True,
        #     cwd=working_directory,  # Change working directory
        #     env=my_env,
        # )

        # Get the current date and time
        now = datetime.datetime.now()
        # Convert it to a string
        current_time = now.strftime("%Y%m%d%H%M%S")

        #
        watchdog_logs_folder = config["watchdog"]["logs_folder"]
        os.makedirs(f"{watchdog_logs_folder}/per-run/{pipeline}", exist_ok=True)

        with open(
            f"{watchdog_logs_folder}/per-run/{pipeline}/{date_folder}_{current_time}.log",
            "w",
        ) as f:
            process = subprocess.Popen(
                cmd + profile_dry_run + dry_run_options,
                stdout=f,
                stderr=f,
                universal_newlines=True,
                cwd=working_directory,  # Change working directory
                env=my_env,
            )

            # Variable to store the penultimate line
            # penultimate_line = ""

            # Read the output line by line in real-time
            # for line in iter(process.stdout.readline, ""):
            #     print(line.strip())  # log line in real-time
            #     if line.strip():  # If line is not blank
            #         penultimate_line = line.strip()

            # Wait for the subprocess to finish
            process.wait()
            print("Return code: %s", process.returncode)

            # Check the penultimate line
            if str(process.returncode) == str(0):
                # self.run_second_command(cmd, profile_slurm, data_location, date_folder)
                run_second_command(
                    cmd,
                    wms_monitor_args,
                    profile_slurm,
                    profile_dry_run,
                    data_location,
                    date_folder,
                    working_directory,
                    my_env,
                    report_location,
                    pipeline,
                )
            else:
                print("\nThe output is not as expected.")

    def run_second_command(
        cmd,
        wms_monitor_args,
        profile_slurm,
        profile_dry_run,
        data_location,
        date_folder,
        working_directory,
        my_env,
        report_location,
        pipeline,
    ):
        """Run the second command and write the output to a log file."""

        print("\nThe output is as expected.")
        print("Running command: %s", " ".join(cmd))

        report_options = [
            "--report",
            f"{report_location}",
            "--report-stylesheet",
            "/g/korbel2/weber/workspace/mosaicatcher-update/workflow/report/custom-stylesheet.css",
        ]

        watchdog_logs_folder = config["watchdog"]["logs_folder"]

        # Get the current date and time
        now = datetime.datetime.now()

        # Convert it to a string
        current_time = now.strftime("%Y%m%d%H%M%S")

        # print("Running mosaicatcher for real")
        # print(cmd + profile_slurm + wms_monitor_args)
        # print(" ".join(cmd + profile_slurm + wms_monitor_args))

        # with open(
        #     f"{watchdog_logs_folder}/per-run/{pipeline}/{date_folder}_{current_time}.log",
        #     "w",
        # ) as f:
        #     process2 = subprocess.Popen(
        #         # cmd,
        #         cmd + profile_slurm + wms_monitor_args,
        #         stdout=f,
        #         stderr=f,
        #         universal_newlines=True,
        #         cwd=working_directory,  # Change working directory
        #         env=my_env,
        #     )
        #     process2.wait()

        #     print("Return code: %s", process2.returncode)

        # logging.info("Generating ashleys report.")
        # print(report_location)
        # print(os.path.dirname(report_location))
        # os.makedirs(os.path.dirname(report_location), exist_ok=True)

        # os.makedirs(f"{publishdir_location}/{date_folder}/{sample}/reports/", exist_ok=True)
        logging.info(
            "Running command: %s", " ".join(cmd + profile_slurm + report_options)
        )

        # Change the permissions of the new directory
        # subprocess.run(["chmod", "-R", "777", f"{data_location}/{date_folder}"])

        print("Running command: %s", " ".join(cmd + profile_slurm + report_options))

        with open(
            f"{watchdog_logs_folder}/per-run/{pipeline}/{date_folder}_{current_time}_report.log",
            "w",
        ) as f:
            print(cmd + profile_slurm + report_options)
            process2 = subprocess.Popen(
                cmd + profile_dry_run + report_options,
                stdout=f,
                stderr=f,
                universal_newlines=True,
                cwd=working_directory,  # Change working directory
                env=my_env,
            )
            # process2 = subprocess.Popen(cmd + profile_slurm + report_options, stdout=f, stderr=f, universal_newlines=True)
            process2.wait()

            logging.info("Return code: %s", process2.returncode)

        # ZIPFILE

        import zipfile

        # Check if the file exists and is a valid zip file
        if zipfile.is_zipfile(report_location):
            # Specify the directory where you want to extract the contents
            # If you want to extract in the same directory as the zip file, just use the parent directory
            extract_location = "/".join(report_location.split("/")[:-1])

            # Extract the zip file
            with zipfile.ZipFile(report_location, "r") as zip_ref:
                zip_ref.extractall(extract_location)
            print(f"Extracted the archive to {extract_location}")
        else:
            print(f"{report_location} is not a valid zip file.")

        # Change the permissions of the new directory
        subprocess.run(["chmod", "-R", "777", f"{data_location}/{date_folder}"])

    ############
    # START
    ############

    # Settings & variables

    data_location = config["data"]["complete_data_folder"]
    publishdir_location = config["data"]["data_folder"]
    # profile_slurm = ["--profile", "/g/korbel2/weber/workspace/snakemake_profiles/HPC/dev/slurm_legacy_conda/"]
    profile_slurm = [
        "--profile",
        "/g/korbel2/weber/workspace/snakemake_profiles/HPC/slurm_EMBL/",
    ]
    profile_dry_run = [
        "--profile",
        "/g/korbel2/weber/workspace/snakemake_profiles/local/conda/",
    ]
    dry_run_options = ["-c", "1", "-n", "-q"]
    snakemake_binary = config["snakemake"]["binary"]
    # snakemake_binary = "/Users/tweber/miniconda3/envs/snakemake_latest/bin/snakemake"
    wms_monitor_options = config["panoptes"]["url"]
    wms_monitor_renaming_option = f"name={run_id}"
    run_name = f"{run_id}".split("--")[1]
    sample_name = f"{run_id}".split("--")[2]
    pipeline = "mosaicatcher-pipeline"
    report_location = f"{publishdir_location}/{run_name}/{sample_name}/reports/{sample_name}_{pipeline}_report.zip"

    cmd = [
        f"{snakemake_binary}",
        "--snakefile",
        "workflow/Snakefile",
        "--nolock",
        "--config",
        "genecore=True",
        # f"genecore_prefix={genecore_prefix}",
        f"genecore_date_folder={run_name}",
        # f"genecore_regex_element={prefix}",
        f'samples_to_process="[{sample_name}]"',
        # "multistep_normalisation=True",
        # "MultiQC=True",
        # "split_qc_plot=False",
        "ashleys_pipeline=True",
        # f"publishdir={publishdir_location}",
        # "email=thomas.weber@embl.de",
        f"data_location={data_location}",
    ]

    # Debug

    # cmd = [
    #     f"{snakemake_binary}",
    #     "--nolock",
    #     # "--rerun-triggers mtime",
    #     "--forceall",
    #     "--cores",
    #     "1",
    #     "--config",
    #     # "blacklisting=False",
    #     # "split_qc_plot=False",
    #     # # f"publishdir={publishdir_location}",
    #     # # "email=thomas.weber@embl.de",
    #     # f"data_location={data_location}",
    #     # f'samples_to_process="[{sample_name}]"',
    # ]

    # Panoptes

    wms_monitor_args = [
        "--wms-monitor-arg",
        f"{wms_monitor_renaming_option}",
        "--wms-monitor",
        f"{wms_monitor_options}",
    ]

    # Append the snake_args to cmd
    snake_args_list = list()
    for key, value in snake_args.items():
        if value is not None:
            snake_args_list.append(f"{key}={value}")

    cmd = cmd + snake_args_list
    cmd = cmd + [
        "--rerun-triggers",
        "mtime",
    ]
    print(cmd)

    # Triggers snakemake command
    # execute_command(directory_path, prefixes.pop())
    execute_command(
        cmd=cmd,
        profile_dry_run=profile_dry_run,
        profile_slurm=profile_slurm,
        dry_run_options=dry_run_options,
        wms_monitor_args=wms_monitor_args,
        data_location=config["data"]["complete_data_folder"],
        date_folder=run_name,
        working_directory=config["snakemake"]["repository_location"],
        report_location=report_location,
        # working_directory="/Users/tweber/Gits/snakemake_logs_dev",
        pipeline=pipeline,
        sample_name=sample_name,
        publishdir_location=publishdir_location,
    )


@app.get("/reports/{run}--{sample}/{pipeline}/report.html")
def serve_report(pipeline: str, run: str, sample: str):
    data_folder = config["data"]["data_folder"]
    file_path = (
        f"{data_folder}/{run}/{sample}/reports/{sample}_{pipeline}_report/report.html"
    )
    print(file_path)

    # Check if the file exists
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="text/html")
    else:
        return {"error": "File not found!"}


@app.get("/reports/{run}--{sample}/{pipeline}/data/{resource_path:path}")
def serve_report_resources(pipeline: str, run: str, sample: str, resource_path: str):
    data_folder = config["data"]["data_folder"]
    file_path = f"{data_folder}/{run}/{sample}/reports/{sample}_{pipeline}_report/data/{resource_path}"
    print(file_path)

    # Check if the file exists
    if os.path.exists(file_path) and os.path.isfile(
        file_path
    ):  # Make sure it's a file and not a directory
        if file_path.endswith(".html"):
            return FileResponse(file_path, media_type="text/html")
        # Add more conditions for other file types if necessary
        else:
            return FileResponse(file_path)
    else:
        return {"error": "File not found!"}
