import glob
import logging
import pandas as pd
import collections
from datetime import datetime
import os
import re
import pika
import time
import httpx
import json
from config import load_config
import yaml

config = load_config()


def fetch_data_from_api():
    # PANOPTES_API = "http://127.0.0.1:8058"
    PANOPTES_API = config["panoptes"]["url"]
    url_api = f"{PANOPTES_API}/api/workflows"
    max_retries = 5
    wait_time = 10

    # with httpx.Client() as client:  # Changed this line
    #     for attempt in range(max_retries):
    try:
        response = httpx.Client().get(url_api, headers={"Accept": "application/json"})
        response.raise_for_status()  # Raise exception for HTTP errors
        response_json = response.json()
        return response_json
    except httpx.ReadTimeout:  # Catching ReadTimeout
        # if attempt == max_retries - 1:
        print(f"Failed to fetch progress from API after {max_retries} attempts.")

        return {}
        # return data
        # print(
        #     f"Timeout error: Attempt {attempt + 1} of {max_retries}. Retrying in {wait_time} seconds."
        # )
        # time.sleep(wait_time)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # print("Loading from JSON file...")
        # data = load_from_json()
        # print(data)
        return {}
        # return data


def find_workflow_id_by_name(workflows, name):
    for workflow in workflows.get("workflows", []):
        if workflow["name"] == name:
            return workflow
    return None


# Function to load YAML configuration
def load_config(file_path):
    with open(file_path, "r") as file:
        return yaml.safe_load(file)


def extract_samples_names(l, directory_path):
    samples = list()
    prefixes = list()
    plate_types = list()

    pattern = re.compile(r"_lane1(.*?)(iTRU|PE20)(.*?)([A-H]?)(\d{2})(?:_1_|_2_)")

    # First pass: Count occurrences of each sample_name
    file_counts_per_sample = collections.Counter()
    for file_path in l:
        match = pattern.search(file_path)
        if match:
            sample_name = match.group(1)
            file_counts_per_sample[sample_name] += 1

    # print(directory_path)
    # print(file_counts_per_sample)

    # Second pass: Process files and determine plate type per sample
    for j, file_path in enumerate(sorted(l)):
        match = pattern.search(file_path)
        if match:
            sample_name = match.group(1)

            file_count = file_counts_per_sample[sample_name]

            # Determine plate type using modulo 96 operation
            if file_count % 96 != 0:
                # raise ValueError(
                print(
                    f"Invalid file count for sample {sample_name} with file count {file_count}. Must be a multiple of 96."
                )
                continue
            plate_type = int(file_count / 2)

            if (j + 1) % file_count == 0:
                if not sample_name or len(sample_name) == 0:
                    continue
                prefixes.append(match.group(2))
                plate = directory_path.split("/")[-1]
                samples.append(sample_name)
                plate_types.append(plate_type)

    return prefixes, samples, plate_types


# Function to process each sample
def process_sample(
    sample_name,
    plate,
    pipeline,
    data_location,
    publishdir_location,
    variable,
    workflows_data,
    last_message_timestamp,
    prefixes,
    plate_type,
):
    run_id = f"{pipeline}--{plate}--{sample_name}"
    workflow_id = find_workflow_id_by_name(workflows_data, run_id)

    dict_variables = {
        f"{variable}_scratch": False,
        f"{variable}_scratch_ts": False,
        f"{variable}_scratch_rdays": None,
        f"{variable}_report": False,
    }

    # ashleys_final_scratch = False
    # ashleys_report = False
    # ashleys_final_scratch_timestamp = None
    # ashleys_rdays = None

    # mosaicatcher_final_scratch = False
    # mosaicatcher_report = False
    # mosaicatcher_final_scratch_timestamp = None
    # mc_rdays = None

    if os.path.isfile(
        f"{publishdir_location}/{plate}/{sample_name}/reports/{sample_name}_{pipeline}_report.zip"
    ):
        # report = True
        dict_variables[f"{variable}_report"] = True

    if pipeline == "ashleys-qc-pipeline":
        if os.path.isfile(
            f"{data_location}/{plate}/{sample_name}/config/ashleys_final_results.ok"
            # f"{data_location}/{plate}/{sample_name}/multiqc/multiqc_report/multiqc_report.html"
        ):
            # ashleys_final_scratch = True
            ts = os.path.getmtime(
                f"{data_location}/{plate}/{sample_name}/config/ashleys_final_results.ok"
            )
            ts = datetime.fromtimestamp(ts)
            dict_variables[f"{variable}_scratch"] = True
            dict_variables[f"{variable}_scratch_ts"] = ts

            # to datetime and then strfmtime

            # computing remaning days to reach 5 months between ashleys_final_scratch_timestamp and now
            rdays = (datetime.now() - ts).days
            rdays = 150 - rdays

            dict_variables[f"{variable}_scratch_rdays"] = rdays
    elif pipeline == "mosaicatcher-pipeline":
        if os.path.isfile(
            f"{data_location}/{plate}/{sample_name}/plots/final_results/{sample_name}.txt"
            # f"{data_location}/{plate}/{sample_name}/multiqc/multiqc_report/multiqc_report.html"
        ):
            ts = os.path.getmtime(
                f"{data_location}/{plate}/{sample_name}/plots/final_results/{sample_name}.txt"
            )
            ts = datetime.fromtimestamp(ts)
            dict_variables[f"{variable}_scratch"] = True
            dict_variables[f"{variable}_scratch_ts"] = ts
            # to datetime and then strfmtime
            # computing remaning days to reach 5 months between ashleys_final_scratch_timestamp and now
            rdays = (datetime.now() - ts).days
            rdays = 150 - rdays

            dict_variables[f"{variable}_scratch_rdays"] = rdays

    if not workflow_id:
        workflow_id = {
            "id": "None",
            "status": "None",
            "started_at": last_message_timestamp,
            "completed_at": last_message_timestamp,
            "jobs_done": "None",
            "jobs_total": "None",
        }
    else:
        workflow_id["started_at"] = datetime.strptime(
            workflow_id["started_at"],
            "%a, %d %b %Y %H:%M:%S GMT",
        ).strftime("%Y-%m-%d %H:%M:%S.%f")

        if workflow_id["completed_at"] is not None:
            workflow_id["completed_at"] = datetime.strptime(
                workflow_id["completed_at"],
                "%a, %d %b %Y %H:%M:%S GMT",
            ).strftime("%Y-%m-%d %H:%M:%S.%f")

    # turn the print into a dict
    tmp_d = {
        "panoptes_id": workflow_id["id"],
        "plate": plate,
        "sample": sample_name,
        # "report": report,
        # "labels": labels,
        # "ashleys_final_scratch": ashleys_final_scratch,
        # "ashleys_final_scratch_timestamp": ashleys_final_scratch_timestamp,
        # "ashleys_rdays": ashleys_rdays,
        # "mosaicatcher_final_scratch": mosaicatcher_final_scratch,
        # "mosaicatcher_final_scratch_timestamp": mosaicatcher_final_scratch_timestamp,
        # "mc_rdays": mc_rdays,
        "report": dict_variables[f"{variable}_report"],
        # "ashleys_final_scratch": ashleys_final_scratch,
        # "ashleys_final_scratch_timestamp": ashleys_final_scratch_timestamp,
        # "ashleys_rdays": ashleys_rdays,
        "final_output_scratch": dict_variables[f"{variable}_scratch"],
        "scratch_ts": dict_variables[f"{variable}_scratch_ts"],
        "scratch_rdays": dict_variables[f"{variable}_scratch_rdays"],
        "status": workflow_id["status"],
        "prefix": list(prefixes)[0],
        "plate_type": plate_type,
        "started_at": workflow_id["started_at"],
        "completed_at": workflow_id["completed_at"],
        "jobs_done": workflow_id["jobs_done"],
        "jobs_total": workflow_id["jobs_total"],
    }
    return tmp_d


# Main function to process directories
def process_directories(
    main_path_to_watch,
    excluded_samples,
    pipeline,
    data_location,
    publishdir_location,
    variable,
    workflows_data,
    last_message_timestamp,
):
    unwanted = ["._.DS_Store", ".DS_Store", "config"]

    main_df = []
    if len(workflows_data) > 0:
        for year in os.listdir(main_path_to_watch):
            if year.startswith("20"):  # Assuming only years are relevant
                path_to_watch = f"{main_path_to_watch}/{year}"
                total_list_runs = sorted(
                    [e for e in os.listdir(path_to_watch) if e not in unwanted]
                )
                for plate in total_list_runs:
                    if plate.split("-")[0][:2] == "20":
                        directory_path = f"{path_to_watch}/{plate}"
                        prefixes, samples, plate_types = extract_samples_names(
                            glob.glob(f"{directory_path}/*.txt.gz"),
                            directory_path,
                        )
                        if len(set(prefixes)) == 1:
                            for sample_name, plate_type in zip(samples, plate_types):
                                if sample_name not in excluded_samples:
                                    result = process_sample(
                                        sample_name,
                                        plate,
                                        pipeline,
                                        data_location,
                                        publishdir_location,
                                        variable,
                                        workflows_data,
                                        last_message_timestamp,
                                        prefixes,
                                        plate_type,
                                    )
                                    main_df.append(result)
    return pd.DataFrame(main_df)


def check_unprocessed_folder():
    # # Get the list of processed plates from rabbitmq
    workflows_data = fetch_data_from_api()
    # message = self.consume_last_message_from_rabbitmq(
    #     json_backup_filename="watchdog/processing_status.json", queue="data_queue"
    # )

    # list_runs_processed = sorted(
    #     [e for e in os.listdir(data_location) if e not in unwanted]
    # )

    # unprocessed_plates = sorted(list(set(total_list_runs).difference(list_runs_processed)))
    unprocessed_plates = list()
    # workflows_data = self.get_workflows()
    # print(message)
    # workflows_data = message[0]
    # last_message_timestamp = message[1]
    # print(last_message_timestamp)
    # last_message_timestamp = datetime.strptime(
    #     last_message_timestamp, "%Y-%m-%d %H:%M:%S"
    # ).strftime("%Y-%m-%d %H:%M:%S.%f")

    # last_message_timestamp = last_message_timestamp

    last_message_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

    pipeline = "mosaicatcher-pipeline"
    main_path_to_watch = "/g/korbel/STOCKS/Data/Assay/sequencing"
    data_location = "/scratch/tweber/DATA/MC_DATA/STOCKS"
    publishdir_location = "/g/korbel/WORKFLOW_RESULTS"

    variable = "aqc" if pipeline == "ashleys-qc-pipeline" else "mc"

    # Get the list of excluded samples from the config
    config = load_config("excluded_samples.yaml")
    # TODO: add run in the excluded list
    excluded_samples = config["excluded_samples"]

    main_df = process_directories(
        main_path_to_watch,
        excluded_samples,
        pipeline,
        data_location,
        publishdir_location,
        variable,
        workflows_data,
        last_message_timestamp,
    )

    pd.options.display.max_rows = 999
    pd.options.display.max_colwidth = 30

    main_df = pd.DataFrame(main_df)
    # main_df.loc[(main_df["labels"] == True) &  (main_df["report"] == True), "real_status"] = "Completed"
    main_df.loc[
        (main_df["final_output_scratch"] == True) & (main_df["report"] == False),
        "real_status",
    ] = "Report missing"
    main_df.loc[
        (main_df["final_output_scratch"] == False) & (main_df["report"] == True),
        "real_status",
    ] = "Partial report"
    main_df.loc[
        (main_df["final_output_scratch"] == False) & (main_df["report"] == False),
        "real_status",
    ] = "To process"
    # main_df.loc[
    #     (main_df["final_output_scratch"] == True)
    #     & (main_df["report"] == True)
    #     & (main_df["status"] == "None"),
    #     "real_status",
    # ] = "Error"
    main_df.loc[
        (main_df["final_output_scratch"] == True)
        & (main_df["report"] == True)
        & (main_df["status"] == "Running"),
        "real_status",
    ] = "Running"
    main_df.loc[
        (main_df["final_output_scratch"] == True) & (main_df["report"] == True)
        # & (main_df["status"] == "Done")
        ,
        "real_status",
    ] = "Completed"
    main_df["real_status"] = main_df["real_status"].fillna("Error (to  investigate))")
    # print(workflows_data["workflows"])

    # print("\n")
    # logging.info(f"Pipeline selected {pipeline}")
    print("\n")

    # print(main_df)
    test_json = main_df.to_json(orient="records", date_format="iso")
    # print(pd.read_json(test_json, orient="records"))
    return test_json


def generate_progress_json():
    response_json = fetch_data_from_api()

    if response_json:
        unwanted = ["._.DS_Store", ".DS_Store", "config"]

        # REPLACE /g/korbel/STOCKS/Data/Assay/sequencing/2023 by /g/korbel/STOCKS/Data/Assay/sequencing to handle both 2023 and 2024

        stocks_path_to_watch = [
            f"{path_to_watch}/{year}"
            for year in os.listdir(main_path_to_watch)
            if year.startswith("20")
        ]

        total_list_runs = sorted(
            [
                e
                for path_to_watch in stocks_path_to_watch
                for e in os.listdir(path_to_watch)
                if e not in unwanted
            ]
        )


def get_files_structure(root_folder):
    unwanted = ["._.DS_Store", ".DS_Store", "config"]
    data_dict = collections.defaultdict(list)
    for run_name_folder in os.listdir(root_folder):
        run_name = run_name_folder
        pattern = "(?:20[1-3][0-9])-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])-.*"
        # Find all matches
        matches = re.findall(pattern, run_name)
        print(run_name, matches)
        if matches:
            print("OK")
            for sample_folder in os.listdir(os.path.join(root_folder, run_name_folder)):
                print(sample_folder)
                if sample_folder not in unwanted:
                    sample_name = sample_folder
                    data_dict[run_name].append(sample_name)

    return data_dict


def publish_to_rabbitmq(data=dict, exchange=str, queue=str, routing_key=str):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(config["rabbitmq_general_settings"]["hostname"])
    )
    channel = connection.channel()

    # Declare a topic exchange
    channel.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)

    # Declare a queue named 'my_queue' with a message TTL of 300000 milliseconds (5 minutes)
    args = {"x-message-ttl": 30000}
    channel.queue_declare(queue=queue, durable=True, arguments=args)

    # Bind the queue to the exchange with the routing key 'latest_status'
    channel.queue_bind(exchange=exchange, queue=queue, routing_key=routing_key)

    # Fetch the current timestamp
    current_timestamp = int(
        datetime.now().timestamp() * 1000
    )  # Current time in milliseconds

    # Publish the message to the exchange with the 'latest_status' routing key
    channel.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=json.dumps(data),
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
            timestamp=current_timestamp,  # set timestamp
        ),
    )

    connection.close()


def save_to_json(data=dict, filename=str):
    with open(filename, "w") as file:
        json.dump(data, file)


if __name__ == "__main__":
    while True:
        # Wf progress status - Panoptes
        data = check_unprocessed_folder()
        # data = fetch_data_from_api()
        if data != {}:
            print(config["panoptes"]["json_status_backup"])
            save_to_json(data=data, filename=config["panoptes"]["json_status_backup"])

        publish_to_rabbitmq(
            data=data,
            exchange=config["panoptes"]["rabbitmq"]["exchange"],
            queue=config["panoptes"]["rabbitmq"]["queue"],
            routing_key=config["panoptes"]["rabbitmq"]["routing_key"],
        )

        # Data structure
        data_dict = get_files_structure(config["data"]["data_folder"])
        if data_dict != {}:
            print(config["data"]["json_data_backup"])
            save_to_json(data=data_dict, filename=config["data"]["json_data_backup"])

        publish_to_rabbitmq(
            data=data_dict,
            exchange=config["data"]["rabbitmq"]["exchange"],
            queue=config["data"]["rabbitmq"]["queue"],
            routing_key=config["data"]["rabbitmq"]["routing_key"],
        )

        data_panoptes = fetch_data_from_api()

        publish_to_rabbitmq(
            data=data_panoptes,
            exchange="panoptes",
            queue="data_panoptes",
            routing_key="latest_panoptes",
        )

        # Fetch every 30 seconds
        time.sleep(25)
