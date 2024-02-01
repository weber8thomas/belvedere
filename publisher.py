import glob
import hashlib
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


paths_to_watch = [
    # "/g/korbel/shared/data/others/StrandSeq/runs",
    # "/g/korbel/shared/genecore",
    "/g/korbel/STOCKS/Data/Assay/sequencing",
]


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

    # Compute the hash at the folder level
    hash = hashlib.sha256()
    # List all files in the directory and sort them
    files = glob.glob(f"{directory_path}/*")
    files.sort()
    # Loop over the sorted list of files and update the hash
    for file in files:
        # Get file attributes: name, modification timestamp, and size
        stats = os.stat(file)
        file_info = f"{os.path.basename(file)}-{stats.st_mtime}-{stats.st_size}"

        hash.update(file_info.encode("utf-8"))

    # Get the final hash value in hexadecimal format
    folder_hash = hash.hexdigest()

    return prefixes, samples, plate_types, folder_hash


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
    folder_hash,
):
    run_id = f"{pipeline}--{plate}--{sample_name}"
    workflow_id = None
    # workflow_id = find_workflow_id_by_name(workflows_data, run_id)

    dict_variables = {
        f"{variable}_scratch": False,
        f"{variable}_scratch_ts": False,
        f"{variable}_scratch_rdays": None,
        # f"aqc_report": False,
        f"mc_report": False,
    }

    if os.path.isfile(
        f"{publishdir_location}/{plate}/{sample_name}/reports/{sample_name}_{pipeline}_report.zip"
    ):
        # report = True
        variable = "aqc" if pipeline == "ashleys-qc-pipeline" else "mc"

        dict_variables[f"{variable}_report"] = True

    # if pipeline == "ashleys-qc-pipeline":
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
    # elif pipeline == "mosaicatcher-pipeline":
    info_file = f"{data_location}/{plate}/{sample_name}/counts/{sample_name}.info"
    nb_usable_cells = None
    snp_file = f"{data_location}/{plate}/{sample_name}/snv_calls/check_SNVs_nb.txt"
    check_snp = None

    if os.path.isfile(info_file):
        nb_usable_cells = pd.read_csv(info_file, sep="\t", skiprows=13).shape[0]

    if os.path.isfile(snp_file):
        nb_snps = pd.read_csv(snp_file, sep="\t")
        check_snp = nb_snps.loc[nb_snps["SNP_nb"] > 100].shape[0] == nb_snps.shape[0]
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
            # "started_at": last_message_timestamp,
            # "completed_at": last_message_timestamp,
            # "jobs_done": "None",
            # "jobs_total": "None",
        }
    # else:
    #     workflow_id["started_at"] = datetime.strptime(
    #         workflow_id["started_at"],
    #         "%a, %d %b %Y %H:%M:%S GMT",
    #     ).strftime("%Y-%m-%d %H:%M:%S.%f")

    #     if workflow_id["completed_at"] is not None:
    #         workflow_id["completed_at"] = datetime.strptime(
    #             workflow_id["completed_at"],
    #             "%a, %d %b %Y %H:%M:%S GMT",
    #         ).strftime("%Y-%m-%d %H:%M:%S.%f")

    # turn the print into a dict
    tmp_d = {
        "panoptes_id": workflow_id["id"],
        "plate": plate,
        "sample": sample_name,
        # "report_aqc": dict_variables[f"aqc_report"],
        "report_mc": dict_variables[f"mc_report"],
        "final_output_scratch": dict_variables[f"{variable}_scratch"],
        "nb_usable_cells": nb_usable_cells,
        "check_snp": check_snp,
        "scratch_ts": dict_variables[f"{variable}_scratch_ts"],
        "scratch_rdays": dict_variables[f"{variable}_scratch_rdays"],
        # "status": workflow_id["status"],
        "prefix": list(prefixes)[0],
        "plate_type": plate_type,
        "folder_hash": folder_hash,
        # "started_at": workflow_id["started_at"],
        # "completed_at": workflow_id["completed_at"],
        # "jobs_done": workflow_id["jobs_done"],
        # "jobs_total": workflow_id["jobs_total"],
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
    ref_df,
):
    unwanted = ["._.DS_Store", ".DS_Store", "config"]

    if ref_df.empty is False:
        ref_df_plates = ref_df["plate"].unique().tolist()
    else:
        ref_df_plates = []

    main_df = []
    # if len(workflows_data) > 0:
    total_list_runs = []

    for path_to_watch in paths_to_watch:
        if path_to_watch == "/g/korbel/STOCKS/Data/Assay/sequencing":
            for year in os.listdir(path_to_watch):
                if year.startswith(
                    "20"
                ):  # Assuming directories starting with "20" are years
                    year_path = os.path.join(path_to_watch, year)
                    for folder in os.listdir(year_path):
                        folder_path = os.path.join(year_path, folder)
                        if os.path.isdir(folder_path) and folder not in unwanted:
                            total_list_runs.append(folder_path)
        else:
            for e in os.listdir(path_to_watch):
                if e not in unwanted and os.path.isdir(os.path.join(path_to_watch, e)):
                    total_list_runs.append(os.path.join(path_to_watch, e))

    # exclude plates from the ref_df in the total_list_runs
    print(total_list_runs)
    print("EXCLUDE")

    total_list_runs = sorted(list(set(total_list_runs).difference(set(ref_df_plates))))
    print(total_list_runs)

    for directory_path in total_list_runs:
        print(directory_path)
        prefixes, samples, plate_types, folder_hash = extract_samples_names(
            glob.glob(f"{directory_path}/*.txt.gz"),
            directory_path,
        )
        print(
            f"Samples: {samples}, Prefixes: {prefixes}, Plate Types: {plate_types}, Folder Hash: {folder_hash}"
        )

        if len(set(prefixes)) == 1:
            for sample_name, plate_type in zip(samples, plate_types):
                if sample_name not in excluded_samples:
                    os.makedirs(
                        f"{publishdir_location}/{os.path.basename(directory_path)}/{sample_name}/reports",
                        exist_ok=True,
                    )
                    result = process_sample(
                        sample_name,
                        os.path.basename(directory_path),
                        pipeline,
                        data_location,
                        publishdir_location,
                        variable,
                        workflows_data,
                        last_message_timestamp,
                        prefixes,
                        plate_type,
                        # path_to_watch,
                        folder_hash,
                    )
                    main_df.append(result)
    return pd.DataFrame(main_df)


def check_unprocessed_folder():
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

    ref_df_file = "ref_test.tsv"

    # if os.path.isfile(ref_df_file):
    #     print("READING")
    #     ref_df = pd.read_csv(ref_df_file, sep="\t")
    #     print(ref_df)
    #     # exit()

    # else:
    ref_df = pd.DataFrame()

    # save output to json file
    main_df = process_directories(
        main_path_to_watch,
        excluded_samples,
        pipeline,
        data_location,
        publishdir_location,
        variable,
        [],
        last_message_timestamp,
        ref_df,
    )

    pd.options.display.max_rows = 999
    pd.options.display.max_colwidth = 70

    main_df = pd.DataFrame(main_df)
    # main_df.loc[(main_df["labels"] == True) &  (main_df["report"] == True), "real_status"] = "Completed"
    # main_df.loc[
    #     (main_df["final_output_scratch"] == True) & (main_df["report_mc"] == False),
    #     "real_status",
    # ] = "MC Report missing"
    # main_df.loc[
    #     (main_df["final_output_scratch"] == False) & (main_df["report_mc"] == True),
    #     "real_status",
    # ] = "Error"
    # main_df.loc[
    #     (main_df["final_output_scratch"] == False) & (main_df["report_mc"] == False),
    #     "real_status",
    # ] = "To process"
    # main_df.loc[
    #     (main_df["final_output_scratch"] == True)
    #     & (main_df["report_mc"] == True)
    #     & (main_df["status"] == "None"),
    #     "real_status",
    # ] = "Error"
    # main_df.loc[
    #     (main_df["final_output_scratch"] == True)
    #     & (main_df["report_mc"] == True)
    #     & (main_df["status"] == "Running"),
    #     "real_status",
    # ] = "Running"
    # main_df.loc[
    #     (main_df["final_output_scratch"] == True)
    #     & (main_df["report_mc"] == True)
    #     & (main_df["status"] == "Done"),
    #     "real_status",
    # ] = "Completed"
    # main_df["real_status"] = main_df["real_status"].fillna("Error (to  investigate))")
    # print(workflows_data["workflows"])
    main_df = main_df.sort_values(by=["plate", "sample"])
    print(main_df)

    main_df.to_csv("ref_test.tsv", sep="\t", index=False)

    # print("\n")
    # logging.info(f"Pipeline selected {pipeline}")
    print("\n")

    test_json = main_df.to_json(orient="records", date_format="iso")

    # print(pd.read_json(test_json, orient="records"))
    return test_json


# def generate_progress_json():
#     response_json = fetch_data_from_api()

#     if response_json:
#         unwanted = ["._.DS_Store", ".DS_Store", "config"]

#         # REPLACE /g/korbel/STOCKS/Data/Assay/sequencing/2023 by /g/korbel/STOCKS/Data/Assay/sequencing to handle both 2023 and 2024

#         stocks_path_to_watch = [
#             f"{path_to_watch}/{year}"
#             for year in os.listdir(main_path_to_watch)
#             if year.startswith("20")
#         ]

#         total_list_runs = sorted(
#             [
#                 e
#                 for path_to_watch in stocks_path_to_watch
#                 for e in os.listdir(path_to_watch)
#                 if e not in unwanted
#             ]
#         )


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
        print(data)
        exit()
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
