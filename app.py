# IMPORTS
import glob
from io import BytesIO, StringIO
import sys
import threading
import collections
from datetime import datetime
import json
import random
import re
from dash_iconify import DashIconify
import subprocess
from dash import Dash, html, dcc, Input, Output, State, ALL, MATCH, ALLSMALLER
import os
import pandas as pd
import dash_bootstrap_components as dbc
import dash
import dash_ag_grid as dag
from pprint import pprint
import pika
import plotly
import requests
import yaml
import time
import dash_mantine_components as dmc
from dash import html, Output, Input, State
import dash_auth
import yaml
import plotly.express as px
import redis

from dotenv import load_dotenv

load_dotenv()


redis_client = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
)


VALID_USERNAME_PASSWORD_PAIRS = {
    os.getenv("USERNAME"): os.getenv("PASSWORD_STRANDSCAPE"),
}

# STRAND-SCAPE utils
from utils import merge_labels_and_info, get_files_structure
from utils import columnDefs, defaultColDef, SIDEBAR_STYLE, CONTENT_STYLE

# Initializing Dash application with specific configurations and styles
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Strand-Scape",
    update_title=None,
)

auth = dash_auth.BasicAuth(app, VALID_USERNAME_PASSWORD_PAIRS)

# server = app.server

from config import load_config

config = load_config("config.yaml")
root_folder = os.path.expanduser(config["data"]["data_folder"])

# data = get_files_structure(root_folder)


# Fetching the file structure based on the root folder
def fetch_data():
    FASTAPI_HOST = config["fastapi"]["host"]
    FASTAPI_PORT = config["fastapi"]["port"]

    if redis_client.exists("fetch_data"):
        # print("FETCH DATA exists in Redis")

        # Get the figure from Redis
        response_json_complete = redis_client.get("fetch_data")
        timestamp = redis_client.get("timestamp_fetch_data")

        # Deserialize the JSON back to a Plotly figure
        # Since Redis returns data in bytes, we need to convert it to a string
        response_json_complete = json.loads(response_json_complete)

    else:
        # print("FETCH DATA does not exist in Redis")

        response = requests.get(f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/get-data")
        response_json_complete = response.json()[0]
        timestamp = response.json()[1]

        # response_json_complete = response_json_complete[0].items()
        # print(response_json_complete)

        # Store the figure in Redis
        # Assuming the key for storing the figure is 'my_figure'
        redis_client.set("fetch_data", json.dumps(response_json_complete), ex=60)
        redis_client.set("timestamp_fetch_data", timestamp, ex=60)

    # timestamp = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")
    # print("TIME STAMP")
    # print(timestamp)
    # print(response_json_complete, type(response_json_complete))
    response_json = collections.OrderedDict(
        # sorted(
        response_json_complete,
        #     # key=lambda x: list(response_json_complete[0].keys()).index(x),
        #     reverse=True,
        # )
    )

    # print(response_json)
    response_json = {
        k: v for k, v in response_json.items() if "2023" in k or "2024" in k
    }

    # print("SORTED DICT")
    # print(response_json)
    # print(timestamp)
    return response_json, timestamp


def generate_data_file(directory):
    # Define the directory containing the files

    # Pattern to match the files
    pattern = re.compile(
        r"\/g\/korbel\/WORKFLOW_RESULTS\/202[0-3]-\d{2}-\d{2}-.*\/(.*)\/counts\/\1.info_raw"
    )

    # Initialize an empty DataFrame to store aggregated data
    df_aggregated = pd.DataFrame()

    # Iterate over the files in the main directory

    unwanted = ["._.DS_Store", ".DS_Store", "config"]

    total_list_runs = sorted([e for e in os.listdir(directory) if e not in unwanted])
    print(total_list_runs)

    l_df = list()

    for plate in total_list_runs:
        if plate.split("-")[0] in ["2023", "2024"]:
            for sample in os.listdir(os.path.join(directory, plate)):
                if "sample" not in unwanted:
                    counts_stats_file_path = os.path.join(
                        directory, plate, sample, "counts", f"{sample}.info_raw"
                    )
                    labels_file_path = os.path.join(
                        directory, plate, sample, "cell_selection", "labels.tsv"
                    )

                    if os.path.isfile(counts_stats_file_path):
                        if os.path.isfile(labels_file_path):
                            # print(counts_stats_file_path)
                            tmp_df_stats = pd.read_csv(
                                counts_stats_file_path, sep="\t", skiprows=13
                            )
                            tmp_df_stats["depictio_run_id"] = plate
                            tmp_df_labels = pd.read_csv(labels_file_path, sep="\t")
                            tmp_df_labels["depictio_run_id"] = plate
                            tmp_df_labels["cell"] = tmp_df_labels["cell"].str.replace(
                                ".sort.mdup.bam", ""
                            )
                            tmp_df = tmp_df_stats.merge(
                                tmp_df_labels, on=["depictio_run_id", "sample", "cell"]
                            )
                            l_df.append(tmp_df)

    l_df = pd.concat(l_df)
    l_df["year"] = l_df["depictio_run_id"].apply(lambda r: r.split("-")[0])
    l_df.to_parquet(
        "/g/korbel2/weber/workspace/strandscape/strandscape_vizu_dev.parquet"
    )


def consume_last_message_from_rabbitmq(queue=str):
    pika_connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="localhost")
    )
    channel = pika_connection.channel()

    # Fetch the message without auto acknowledgment
    method_frame, header_frame, body = channel.basic_get(queue=queue, auto_ack=False)

    if method_frame:
        # Extract the timestamp from the header frame
        timestamp = header_frame.timestamp
        human_readable_timestamp = datetime.fromtimestamp(timestamp / 1000.0).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # # Acknowledge the message after processing
        channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
        data = json.loads(body.decode("utf-8"))
        print(data)
        if not data:
            print("EXITING")
            sys.exit("RabbitMQ queue NOT empty but message is")
        else:
            print("RabbitMQ queue NOT empty and message is NOT empty")
            print(data)
            return data, human_readable_timestamp


def load_data_from_redis(redis_key):
    if redis_client.exists(redis_key):
        # print(f"DF - FETCH DATA exists in Redis for {redis_key}")
        body = redis_client.get(redis_key)
        return pd.read_json(StringIO(body.decode("utf-8")), orient="records")
    else:
        return None


def load_data_from_file(file_path):
    # print(f"DF - FETCH DATA does not exist in Redis for {file_path}")
    df = pd.read_parquet(file_path)
    df = df.loc[df["depictio_run_id"].str.contains("2023|2024")]
    return df


def store_data_in_redis(redis_key, df, expiry=60):
    redis_client.set(redis_key, df.to_json(orient="records"), ex=expiry)


def load_data_for_vizu():
    redis_key = "strandscape_vizu_dev.parquet"
    file_path = "strandscape_vizu_dev.parquet"

    df = load_data_from_redis(redis_key)
    if df is None:
        df = load_data_from_file(file_path)

        sample_list = [sub_e for k, v in fetch_data()[0].items() for sub_e in v]
        if df["sample"].nunique() < len(sample_list):
            print("Updating data file")
            print(
                f"Nb of samples in data file: {df['sample'].nunique()} ; Nb of samples in RabbitMQ: {len(fetch_data()[0].keys())}"
            )
            generate_data_file(config["data"]["data_folder"])
            df = load_data_from_file(file_path)

        store_data_in_redis(redis_key, df)
    df["prediction"] = df["prediction"].astype(str)
    # print(df.prediction.dtype)
    return df


def trigger_snakemake_api(pipeline, run, sample, snake_args):
    FASTAPI_HOST = config["fastapi"]["host"]
    FASTAPI_PORT = config["fastapi"]["port"]

    response = requests.post(
        f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/trigger-snakemake/{pipeline}--{run}--{sample}",
        json=snake_args,
    )

    # Check the response
    print(response.status_code)
    print(response.json())


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
                raise ValueError(
                    f"Invalid file count for sample {sample_name} with file count {file_count}. Must be a multiple of 96."
                )
            plate_type = int(file_count / 2)

            if (j + 1) % file_count == 0:
                prefixes.append(match.group(2))
                plate = directory_path.split("/")[-1]
                samples.append(sample_name)
                plate_types.append(plate_type)

    return prefixes, samples, plate_types


# def custom_status():
#     # get progress from API
#     def get_progress():
#         FASTAPI_HOST = config["fastapi"]["host"]
#         FASTAPI_PORT = config["fastapi"]["port"]

#         response = requests.get(f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/get-progress")
#         response_json = response.json()
#         return response_json

#     workflows_data_progress, last_message_timestamp = get_progress()

#     publishdir_location = config["data"]["data_folder"]
#     data_location = config["data"]["complete_data_folder"]

#     main_df = list()
#     if workflows_data_progress:
#         for workflow in workflows_data_progress["workflows"]:
#             if "--" in workflow["name"]:
#                 pipeline = workflow["name"].split("--")[0]
#                 run = workflow["name"].split("--")[1]
#                 sample = workflow["name"].split("--")[2]

#                 genecore_path = (
#                     config["data"]["genecore_data_folder"]
#                     if run.startswith("2023")
#                     else config["data"]["genecore_data_folder_old"]
#                 )
#                 directory_path = f"{genecore_path}/{run}"

#                 report = False
#                 labels = False
#                 multiqc_scratch = False
#                 multiqc_scratch_timestamp = None
#                 remaining_days = None

#                 if os.path.isfile(
#                     f"{publishdir_location}/{run}/{sample}/cell_selection/labels.tsv"
#                 ):
#                     labels = True

#                 if os.path.isfile(
#                     f"{publishdir_location}/{run}/{sample}/reports/{sample}_{pipeline}_report.zip"
#                 ):
#                     report = True

#                 if os.path.isfile(
#                     f"{data_location}/{run}/{sample}/multiqc/multiqc_report/multiqc_report.html"
#                 ):
#                     multiqc_scratch = True
#                     multiqc_scratch_timestamp = os.path.getmtime(
#                         f"{data_location}/{run}/{sample}/multiqc/multiqc_report/multiqc_report.html"
#                     )
#                     # to datetime and then strfmtime
#                     multiqc_scratch_timestamp = datetime.fromtimestamp(
#                         multiqc_scratch_timestamp
#                     )
#                     # computing remaning days to reach 5 months between multiqc_scratch_timestamp and now
#                     remaining_days = (datetime.now() - multiqc_scratch_timestamp).days
#                     remaining_days = 150 - remaining_days

#                     multiqc_scratch_timestamp = multiqc_scratch_timestamp.strftime(
#                         "%Y-%m-%d"
#                     )

#                 if not workflow:
#                     workflow = {
#                         "id": "None",
#                         "status": "None",
#                         "started_at": last_message_timestamp,
#                         "completed_at": last_message_timestamp,
#                         "jobs_done": "None",
#                         "jobs_total": "None",
#                     }
#                 # else:
#                 #     print(workflow)
#                 #     if workflow["started_at"] is not None:
#                 #         workflow["started_at"] = datetime.strptime(
#                 #             workflow["started_at"],
#                 #             "%a, %d %b %Y %H:%M:%S GMT",
#                 #         ).strftime("%Y-%m-%d %H:%M:%S.%f")
#                 #     else:
#                 #         workflow["started_at"] = last_message_timestamp

#                 #     if workflow["completed_at"] is not None:
#                 #         workflow["completed_at"] = datetime.strptime(
#                 #             workflow["completed_at"],
#                 #             "%a, %d %b %Y %H:%M:%S GMT",
#                 #         ).strftime("%Y-%m-%d %H:%M:%S.%f")
#                 #     else:
#                 #         workflow["completed_at"] = last_message_timestamp

#                 # turn the print into a dict
#                 tmp_d = {
#                     "panoptes_id": workflow["id"],
#                     "pipeline": pipeline,
#                     "run": run,
#                     "sample": sample,
#                     "report": report,
#                     "labels": labels,
#                     "multiqc_scratch": multiqc_scratch,
#                     "multiqc_scratch_timestamp": multiqc_scratch_timestamp,
#                     "remaining_days": remaining_days,
#                     "status": workflow["status"],
#                     # "prefix": list(prefixes)[0],
#                     # "plate_type": plate_type,
#                     "started_at": workflow["started_at"],
#                     "completed_at": workflow["completed_at"],
#                     "jobs_done": workflow["jobs_done"],
#                     "jobs_total": workflow["jobs_total"],
#                 }
#                 main_df.append(tmp_d)
#         pd.options.display.max_rows = 999
#         pd.options.display.max_colwidth = 30
#         # pd.options.display.max_columns = 50
#         main_df = pd.DataFrame(main_df)
#         print(main_df)
#         # main_df.loc[(main_df["labels"] == True) &  (main_df["report"] == True), "real_status"] = "Completed"
#         main_df.loc[
#             (main_df["labels"] == True)
#             & (main_df["report"] == False)
#             & (main_df["multiqc_scratch"] == False),
#             "real_status",
#         ] = "Report missing / /scratch still available"
#         main_df.loc[
#             (main_df["labels"] == False) & (main_df["report"] == True),
#             "real_status",
#         ] = "Error"
#         main_df.loc[
#             (main_df["labels"] == False)
#             & (main_df["report"] == False)
#             & (main_df["multiqc_scratch"] == False),
#             "real_status",
#         ] = "To process"

#         main_df.loc[
#             (main_df["labels"] == False)
#             & (main_df["report"] == False)
#             & (main_df["status"] != "Done"),
#             "real_status",
#         ] = "Uncompleted execution on /scratch"
#         main_df.loc[
#             (main_df["labels"] == True)
#             & (main_df["report"] == False)
#             & (main_df["multiqc_scratch"] == True),
#             "real_status",
#         ] = "Uncompleted execution on /scratch"
#         main_df.loc[
#             (main_df["labels"] == True)
#             & (main_df["report"] == True)
#             & (main_df["status"] == "None"),
#             "real_status",
#         ] = "Error"
#         main_df.loc[
#             (main_df["labels"] == True)
#             & (main_df["report"] == True)
#             & (main_df["status"] == "Running"),
#             "real_status",
#         ] = "Running"
#         main_df.loc[
#             (main_df["labels"] == True)
#             & (main_df["report"] == True)
#             & (main_df["status"] == "Done"),
#             "real_status",
#         ] = "Completed"

#         main_df.loc[
#             (main_df["labels"] == False)
#             & (main_df["report"] == False)
#             & (main_df["multiqc_scratch"] == True),
#             "real_status",
#         ] = "Uncompleted execution on /scratch"
#         main_df["real_status"] = main_df["real_status"].fillna(
#             "Error (to  investigate))"
#         )
#         main_df = main_df.sort_values(by=["pipeline", "run", "sample"])
#         print(main_df)
#         return main_df


# data_panoptes_custom_status = custom_status()
# data_panoptes_custom_status["name"] = data_panoptes_custom_status.apply(
#     lambda r: "--".join([r["pipeline"], r["run"], r["sample"]]), axis=1
# )
# print("data_panoptes_custom_status")
# data_panoptes_custom_status = data_panoptes_custom_status.set_index("name").to_dict(
#     "index"
# )
# print(data_panoptes_custom_status)


@app.callback(
    Output({"type": "embl-login", "index": MATCH}, "error"),
    Output({"type": "save-button", "index": MATCH}, "disabled"),
    Input({"type": "embl-login", "index": MATCH}, "value"),
)
def validate_username(username):
    if username is None or username == "":
        return True, True
    elif username.isalpha():
        return False, False
    else:
        return True, True


# Callback to populate the main content area based on the selected run and sample
@app.callback(
    Output("output-container", "children"),
    Output("output-container", "style"),
    [
        Input("url", "pathname"),
    ],
)
def fill_sample_wise_container(url):
    # If no specific URL path is provided, show the landing page
    if url == "/":
        return html.Div(id="landing-page"), CONTENT_STYLE

    else:
        # If a specific path is provided, extract the selected run and sample from the URL
        selected_run, selected_sample = url.split("/")[1:3]

        # If both the selected run and sample are present
        if selected_run and selected_sample:
            data_folder = config["data"]["data_folder"]

            if os.path.isfile(
                f"{data_folder}/{selected_run}/{selected_sample}/cell_selection/labels.tsv"
            ) and os.path.isfile(
                f"{data_folder}/{selected_run}/{selected_sample}/counts/{selected_sample}.info_raw"
            ):
                files_available = True
            else:
                files_available = False

            if files_available:
                # Fetch and merge necessary data from files
                # TODO: bind to configuration file
                df = merge_labels_and_info(
                    f"{data_folder}/{selected_run}/{selected_sample}/cell_selection/labels.tsv",
                    f"{data_folder}/{selected_run}/{selected_sample}/counts/{selected_sample}.info_raw",
                )

                # Create the offcanvas datatable using dash-ag-grid
                datatable = dag.AgGrid(
                    id={
                        "type": "selection-checkbox-grid",
                        "index": f"{selected_run}--{selected_sample}",
                    },
                    columnDefs=columnDefs,
                    rowData=df.to_dict("records"),
                    defaultColDef=defaultColDef,
                    # selectedRows=df.loc[(df["prediction"] == 1) & (df["pass1"] == 1)].to_dict(
                    #     "records"
                    # ),
                    dashGridOptions={"rowSelection": "multiple"},
                    style={"height": "750px"},
                )

                # Create a modal to display when saving is successful
                modal_save_success = dbc.Modal(
                    [
                        dbc.ModalHeader(
                            html.H1(
                                "Success!",
                                className="text-success",
                            )
                        ),
                        dbc.ModalBody(
                            html.H5(
                                f"Your cell selection for {selected_run} - {selected_sample} was successfully saved!",
                                className="text-success",
                            ),
                            style={"background-color": "#F0FFF0"},
                        ),
                        dbc.ModalFooter(
                            dbc.Button(
                                "Close",
                                id="success-modal-close",
                                className="ml-auto",
                                color="success",
                            )
                        ),
                    ],
                    id="success-modal-dashboard",
                    centered=True,
                )

                # Create an offcanvas (side panel) for cell selection
                offcanvas = dbc.Offcanvas(
                    [
                        dbc.Row(
                            dmc.Center(
                                dmc.TextInput(
                                    id={
                                        "type": "embl-login",
                                        "index": f"{selected_run}--{selected_sample}",
                                    },
                                    label="Your EMBL login",
                                    style={"width": 200},
                                    placeholder="Your EMBL login",
                                    icon=DashIconify(icon="uiw:login"),
                                )
                            )
                        ),
                        html.Hr(),
                        dbc.Row(datatable),
                        dbc.Row(
                            [
                                # dbc.Button(
                                #     "Save", id="save-button", style={"width": "10%", "align": "center"}
                                # ),
                                html.Hr(),
                                dmc.Center(
                                    dmc.Button(
                                        "Save",
                                        id={
                                            "type": "save-button",
                                            "index": f"{selected_run}--{selected_sample}",
                                        },
                                        radius="xl",
                                        variant="filled",
                                        color="green",
                                        n_clicks=0,
                                        size="xl",
                                        leftIcon=DashIconify(icon="bxs:save"),
                                        style={
                                            "width": "20%",
                                            "align": "center",
                                            # "height": "100%",
                                        },
                                    )
                                ),
                                modal_save_success,
                            ]
                        ),
                    ],
                    id={
                        "type": "offcanvas",
                        "index": f"{selected_run}--{selected_sample}",
                    },
                    is_open=False,
                    title="Cell selection",
                    backdrop=True,
                    # header_style={"textAlign": "center"},
                    style={"width": "50%"},
                    placement="end",
                )

                # Load or set default settings/data for various components
                # TODO: move to config file
                data_folder = config["data"]["data_folder"]
                belvedere_json_path = f"{data_folder}/{selected_run}/{selected_sample}/config/strandscape.json"

                if os.path.isfile(belvedere_json_path):
                    sample_json = json.load(open(belvedere_json_path))
                    if "stored-selectedRows" not in sample_json:
                        print(df.loc[(df["prediction"] == 1) & (df["pass1"] == 1)])
                        sample_json["stored-selectedRows"] = df.loc[
                            (df["prediction"] == 1) & (df["pass1"] == 1)
                        ].to_dict("records")
                else:
                    sample_json = {
                        "stored-report-button-ashleys": 0,
                        "stored-save-button": {
                            "n_clicks": 0,
                            "run_mosaicatcher_disabled": True,
                        },
                        "stored-selectedRows": df.loc[
                            (df["prediction"] == 1) & (df["pass1"] == 1)
                        ].to_dict("records"),
                        "stored-homepage-button": 0,
                        "stored-report-button-mosaicatcher": 0,
                        "stored-run-mosaicatcher-button": {
                            "n_clicks": 0,
                            "disabled": True,
                        },
                    }

                # Store settings/data for various components
                stored_components_buttons = html.Div(
                    [
                        dcc.Store(
                            id={
                                "type": "stored-refresh-button-samplewise",
                                "index": f"{selected_run}--{selected_sample}",
                            },
                            data=0,
                            # data=sample_json["stored-refresh-button-samplewise"],
                            storage_type="session",
                        ),
                        dcc.Store(
                            id={
                                "type": "invisible-output",
                                "index": f"{selected_run}--{selected_sample}",
                            },
                            data=0,
                            # data=sample_json["stored-refresh-button-samplewise"],
                            storage_type="session",
                        ),
                        dcc.Store(
                            {
                                "type": "stored-report-button-ashleys",
                                "index": f"{selected_run}--{selected_sample}",
                            },
                            storage_type="session",
                            # data=0,
                            data=sample_json["stored-report-button-ashleys"],
                        ),
                        dcc.Store(
                            {
                                "type": "stored-save-button",
                                "index": f"{selected_run}--{selected_sample}",
                            },
                            storage_type="session",
                            # data={"n_clicks": 0, "run_mosaicatcher_disabled": True},
                            data=sample_json["stored-save-button"],
                        ),
                        dcc.Store(
                            {
                                "type": "stored-selectedRows",
                                "index": f"{selected_run}--{selected_sample}",
                            },
                            storage_type="session",
                            # data=df.loc[
                            #     (df["prediction"] == 1) & (df["pass1"] == 1)
                            # ].to_dict("records"),
                            data=sample_json["stored-selectedRows"],
                        ),
                        dcc.Store(
                            {
                                "type": "stored-homepage-button",
                                "index": f"{selected_run}--{selected_sample}",
                            },
                            storage_type="session",
                            # data=0,
                            data=sample_json["stored-homepage-button"],
                        ),
                        dcc.Store(
                            {
                                "type": "stored-report-button-mosaicatcher",
                                "index": f"{selected_run}--{selected_sample}",
                            },
                            storage_type="session",
                            # data=0,
                            data=sample_json["stored-report-button-mosaicatcher"],
                        ),
                        dcc.Store(
                            {
                                "type": "stored-run-mosaicatcher-button",
                                "index": f"{selected_run}--{selected_sample}",
                            },
                            storage_type="session",
                            # data={"n_clicks": 0, "disabled": True},
                            data=sample_json["stored-run-mosaicatcher-button"],
                        ),
                    ]
                )

                # Create main action buttons (e.g., Save, Refresh, etc.)
                buttons = dmc.Center(
                    dmc.Group(
                        [
                            dmc.Button(
                                "Homepage",
                                id={
                                    "type": "homepage-button",
                                    "index": f"{selected_run}--{selected_sample}",
                                },
                                radius="xl",
                                variant="gradient",
                                n_clicks=0,
                                size="sm",
                                leftIcon=DashIconify(icon="mdi:home"),
                            ),
                            dmc.Button(
                                "Display report",
                                # "Display Ashleys-QC report",
                                id={
                                    "type": "report-button-ashleys",
                                    "index": f"{selected_run}--{selected_sample}",
                                },
                                radius="xl",
                                color="pink",
                                size="sm",
                                n_clicks=0,
                                disabled=True,
                                leftIcon=DashIconify(icon="mdi:eye"),
                            ),
                            dmc.Button(
                                "Cell selection",
                                id={
                                    "type": "open-button",
                                    "index": f"{selected_run}--{selected_sample}",
                                },
                                radius="xl",
                                n_clicks=0,
                                color="orange",
                                disabled=True,
                                size="sm",
                                leftIcon=DashIconify(icon="mdi:hand-tap"),
                            ),
                            dmc.Button(
                                "Run MosaiCatcher",
                                id={
                                    "type": "run-mosaicatcher-button",
                                    "index": f"{selected_run}--{selected_sample}",
                                },
                                radius="xl",
                                color="red",
                                n_clicks=0,
                                disabled=True,
                                size="sm",
                                leftIcon=DashIconify(
                                    icon="ooui:logo-wikimedia-discovery"
                                ),
                                style={"display": "none"},
                            ),
                            dmc.Button(
                                "Display MosaiCatcher report",
                                id={
                                    "type": "report-button-mosaicatcher",
                                    "index": f"{selected_run}--{selected_sample}",
                                },
                                radius="xl",
                                n_clicks=0,
                                color="grape",
                                disabled=True,
                                size="sm",
                                leftIcon=DashIconify(icon="mdi:eye"),
                                style={"display": "none"},
                            ),
                        ],
                    )
                )

                content = [
                    stored_components_buttons,
                    buttons,
                    html.Hr(),
                    html.Div(
                        id={
                            "type": "run-sample-container",
                            "index": f"{selected_run}--{selected_sample}",
                        }
                    ),
                    offcanvas,
                ]

            elif not files_available:
                content = html.Div(
                    [
                        html.H1(
                            "No data available",
                            className="text-danger",
                        ),
                        html.H5(
                            f"No data available yet for {selected_run} - {selected_sample}, please come back later.",
                            className="text-danger",
                        ),
                    ],
                    style=CONTENT_STYLE,
                )

            else:
                content = list()

            # Assemble the main report view for a selected run and sample
            report_wise_div = html.Div(
                [
                    html.Div(
                        dmc.Center(
                            [
                                dmc.Title(
                                    f"Run : {selected_run} - Sample: {selected_sample}",
                                    order=3,
                                    style={
                                        "paddingBottom": "20px",
                                        "paddingTop": "20px",
                                    },
                                ),
                                dcc.Link(
                                    dmc.ActionIcon(
                                        DashIconify(icon="mdi:refresh", width=0),
                                        id={
                                            "type": "refresh-button-samplewise",
                                            "index": f"{selected_run}--{selected_sample}",
                                        },
                                        n_clicks=0,
                                    ),
                                    href=f"/{selected_run}/{selected_sample}",
                                    style={"display": "none", "pointer-events": "none"},
                                    # style={"color": "black", "text-decoration": "none"},
                                ),
                            ],
                        ),
                    ),
                    html.Hr(),
                    html.Div(content),
                ]
            )

            return report_wise_div, CONTENT_STYLE


@app.callback(
    [
        Output("landing-page", "children"),
    ],
    [
        Input("url", "pathname"),
    ],
)
def update_progress(url):
    header_landing_page = dmc.Center(
        [
            dbc.Row(
                [
                    dbc.Col(
                        DashIconify(icon="simple-icons:progress", width=50),
                        width="auto",
                        style={
                            "paddingBottom": "20px",
                            "paddingTop": "20px",
                        },
                    ),
                    dbc.Col(
                        dmc.Title(
                            "Running progress dashboard",
                            order=1,
                            style={
                                "paddingBottom": "20px",
                                "paddingTop": "20px",
                            },
                        ),
                        width="auto",
                    ),
                    dcc.Store(
                        id="stored-refresh-button",
                        data=0,
                        storage_type="session",
                    ),
                    dbc.Col(
                        dcc.Link(
                            dmc.ActionIcon(
                                DashIconify(icon="mdi:refresh", width=0),
                                id="refresh-button",
                                n_clicks=0,
                            ),
                            href="/",
                            style={"display": "none", "pointer-events": "none"},
                            # style={"color": "black", "text-decoration": "none"},
                        ),
                        width="auto",
                        style={"float": "right"},
                    ),
                ],
            ),
        ]
    )

    tmp_data, timestamp = fetch_data()

    dropdown_components = [
        dbc.Col(
            [
                dmc.MultiSelect(
                    id="run-dropdown",
                    placeholder="Select a run",
                    data=[
                        {"label": run, "value": run}
                        for run in sorted(tmp_data.keys(), reverse=False)
                    ],
                    persistence=True,
                    persistence_type="session",
                    # radius="xl",
                    searchable=True,
                    clearable=True,
                    # size="md",
                )
            ],
            width=4,
        ),
        dbc.Col(
            [
                dmc.MultiSelect(
                    id="sample-dropdown",
                    data=[
                        {"label": sample, "value": sample}
                        for run in sorted(tmp_data.keys(), reverse=False)
                        for sample in sorted(tmp_data[run], reverse=False)
                    ],
                    placeholder="Select a sample",
                    persistence=True,
                    persistence_type="session",
                    searchable=True,
                    clearable=True,
                ),
            ],
            width=4,
        ),
        dbc.Col(width=4),
        # dbc.Col(width=3),
    ]

    headers = ["Run", "Sample", "Pipeline completion"]
    # headers = ["Run", "Sample", "Ashleys-QC progress", "MosaiCatcher progress"]
    headers_components = [
        dbc.Col(
            [
                dmc.Text(
                    e,
                    size="lg",
                    weight=700,
                    style={"paddingBottom": "10px"},
                ),
            ],
            width=4,
            style={
                "text-align": "center",
            },
        )
        for e in headers
    ]

    components = [
        html.Div(
            [
                header_landing_page,
                dbc.Row(children=headers_components, style={"paddingBottom": "0px"}),
                dbc.Row(children=dropdown_components, style={"paddingBottom": "20px"}),
                dbc.Spinner(
                    html.Div(id="progress-container-landing-page"),
                    spinner_style={"width": "3rem", "height": "3rem"},
                ),
            ]
        )
    ]

    return components


@app.callback(
    Output("run-dropdown", "value"),
    Input("run-dropdown", "data"),
    prevent_initial_call=True,
)
def set_run_value(options):
    if not options:
        raise dash.exceptions.PreventUpdate
    return options[0]["value"] if options else None


@app.callback(
    Output("sample-dropdown", "data"),
    # Input("year-dropdown", "value"),
    Input("run-dropdown", "data"),
    prevent_initial_call=True,
)
def set_sample_options(selected_run):
    if not selected_run:
        raise dash.exceptions.PreventUpdate
    tmp_data, timestamp = fetch_data()
    sample_names = tmp_data[selected_run]
    return [
        {"label": sample_name, "value": sample_name} for sample_name in sample_names
    ]


@app.callback(
    [
        # Output({"type": "run-mosaicatcher-button", "index": MATCH}, "disabled"),
        Output({"type": "stored-save-button", "index": MATCH}, "data"),
        Output({"type": "stored-selectedRows", "index": MATCH}, "data"),
        Output({"type": "stored-refresh-button-samplewise", "index": MATCH}, "data"),
    ],
    [
        Input({"type": "save-button", "index": MATCH}, "n_clicks"),
        Input({"type": "refresh-button-samplewise", "index": MATCH}, "n_clicks"),
        Input("url", "pathname"),
    ],
    [
        State({"type": "selection-checkbox-grid", "index": MATCH}, "selectedRows"),
        State({"type": "selection-checkbox-grid", "index": MATCH}, "rowData"),
        State({"type": "stored-save-button", "index": MATCH}, "data"),
        State({"type": "stored-selectedRows", "index": MATCH}, "data"),
        State({"type": "stored-refresh-button-samplewise", "index": MATCH}, "data"),
        State({"type": "embl-login", "index": MATCH}, "value"),
    ],
)
def save_selected_rows_and_disable_redirect_button(
    n_clicks,
    n_clicks_refresh,
    url,
    selected_rows,
    df,
    stored_save_button,
    stored_selected_rows,
    stored_refresh_button_samplewise,
    user,
):
    if url != "/":
        print(n_clicks_refresh, stored_refresh_button_samplewise)
        if n_clicks_refresh == 0:
            continue_update = True
        else:
            if n_clicks_refresh > stored_refresh_button_samplewise:
                continue_update = True
            else:
                continue_update = False
        print(continue_update)
        if not continue_update:
            raise dash.exceptions.PreventUpdate
        else:
            run, sample = url.split("/")[1:3]
            processed_df_path = f"{root_folder}/{run}/{sample}/cell_selection/labels_strandscape-{user}.tsv"
            complete_data_folder = config["data"]["complete_data_folder"]
            processed_df_path_scratch = f"{complete_data_folder}/{run}/{sample}/cell_selection/labels_strandscape-{user}.tsv"
            os.makedirs(os.path.dirname(processed_df_path_scratch), exist_ok=True)
            print(processed_df_path)
            print(processed_df_path_scratch)
            print(stored_save_button, stored_selected_rows, n_clicks_refresh)
            # if os.path.isfile(processed_df_path):
            #     return stored_save_button, stored_selected_rows, n_clicks_refresh
            # else:
            # print(stored_save_button)
            if n_clicks:
                print(n_clicks, stored_save_button["n_clicks"])
                if n_clicks > stored_save_button["n_clicks"]:
                    # Convert records to DataFrame once
                    processed_df = pd.DataFrame.from_records(df)

                    # Backup original 'prediction' and 'probability'
                    for col in ["prediction", "probability"]:
                        processed_df[f"{col}_bak"] = processed_df[col]

                    selected_cells = pd.DataFrame.from_records(
                        selected_rows
                    ).cell.values.tolist()

                    # Set 'prediction' and 'probability' directly in processed_df based on condition
                    processed_df.loc[
                        processed_df.cell.isin(selected_cells),
                        ["prediction", "probability"],
                    ] = 1
                    processed_df.loc[
                        ~processed_df.cell.isin(selected_cells),
                        ["prediction", "probability"],
                    ] = 0

                    # Sort and reset index
                    processed_df = processed_df.sort_values(by="cell").reset_index(
                        drop=True
                    )

                    processed_df["cell"] = processed_df["cell"] + ".sort.mdup.bam"

                    processed_df.to_csv(processed_df_path, sep="\t", index=False)
                    processed_df.to_csv(
                        processed_df_path_scratch, sep="\t", index=False
                    )
                    # print(processed_df)
                    stored_save_button["run_mosaicatcher_disabled"] = False
                    print("save_selected_rows_and_disable_redirect_button")
                    print(stored_save_button)
                    return (
                        # stored_save_button["run_mosaicatcher_disabled"],
                        stored_save_button,
                        selected_rows,
                        n_clicks_refresh,
                    )
                else:
                    return (
                        # stored_save_button["run_mosaicatcher_disabled"],
                        stored_save_button,
                        stored_selected_rows,
                        n_clicks_refresh,
                    )
            else:
                return (
                    # stored_save_button["run_mosaicatcher_disabled"],
                    stored_save_button,
                    stored_selected_rows,
                    n_clicks_refresh,
                )
    else:
        raise dash.exceptions.PreventUpdate


# Open the success modal when the Save button is clicked
@app.callback(
    Output("success-modal-dashboard", "is_open"),
    [
        Input({"type": "save-button", "index": ALL}, "n_clicks"),
        Input("success-modal-close", "n_clicks"),
    ],
    [State("success-modal-dashboard", "is_open")],
)
def toggle_success_modal_dashboard(n_save, n_close, is_open):
    ctx = dash.callback_context

    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    # print(trigger_id, n_save, n_close)
    n_save = [e for e in n_save if e is not None]
    print(n_save)

    if "save-button" in trigger_id:
        if n_save is None:
            raise dash.exceptions.PreventUpdate
        else:
            return True

    elif trigger_id == "success-modal-close":
        if n_close is None or n_close == 0:
            raise dash.exceptions.PreventUpdate
        else:
            return False

    return is_open


# Open the offcanvas when the button is clicked
@app.callback(
    Output({"type": "offcanvas", "index": MATCH}, "is_open"),
    Output({"type": "selection-checkbox-grid", "index": MATCH}, "selectedRows"),
    [Input({"type": "open-button", "index": MATCH}, "n_clicks")],
    [
        State({"type": "offcanvas", "index": MATCH}, "is_open"),
        State({"type": "stored-selectedRows", "index": MATCH}, "data"),
    ],
)
def toggle_offcanvas(n, is_open, stored_selected_rows):
    if n:
        print("toggle_offcanvas")
        print(stored_selected_rows)
        return not is_open, stored_selected_rows
    return is_open, stored_selected_rows


@app.callback(
    [
        Output({"type": "report-button-ashleys", "index": MATCH}, "disabled"),
        Output({"type": "open-button", "index": MATCH}, "disabled"),
    ],
    [
        Input("stored-progress", "data"),
        Input("url", "pathname"),
    ],
)
def disable_report_button(progress_store, url):
    if url != "/":
        run, sample = url.split("/")[1:3]
        print(run, sample)
        if progress_store[f"{run}--{sample}"]["ashleys-qc-pipeline"]["status"] in [
            "Completed",
            "Partial report",
        ]:
            return False, False
        else:
            return True, True
    else:
        raise dash.exceptions.PreventUpdate


@app.callback(
    [
        Output({"type": "report-button-mosaicatcher", "index": MATCH}, "disabled"),
        Output({"type": "run-mosaicatcher-button", "index": MATCH}, "disabled"),
    ],
    [
        Input("url", "pathname"),
        Input("stored-progress", "data"),
    ],
    [
        State({"type": "stored-save-button", "index": MATCH}, "data"),
    ],
)
def disable_report_button(url, progress_store, store_save_button):
    if url != "/":
        run, sample = url.split("/")[1:3]
        print("disable_report_button")
        print(run, sample, progress_store[f"{run}--{sample}"])
        print(store_save_button)
        # if (
        #     progress_store[f"{run}--{sample}"]["mosaicatcher-pipeline"]["status"]
        #     == "Done"
        # ):
        #     return False, True
        # else:
        #     if (
        #         progress_store[f"{run}--{sample}"]["ashleys-qc-pipeline"]["status"]
        #         == "Done"
        #     ):
        #         return True, store_save_button["run_mosaicatcher_disabled"]
        #     else:
        return True, True
    else:
        raise dash.exceptions.PreventUpdate


def generate_progress_bar(entry):
    status = entry["status"]
    # if status != "not_started":
    #     progress = round((entry["jobs_done"] / entry["jobs_total"]) * 100, 2)
    # else:
    #     progress = 0

    color = "primary"
    animated = True
    striped = True
    label = ""

    label = f"{status}"
    value = 100
    # if data_panoptes_custom_status[entry["name"]]:
    #     if data_panoptes_custom_status[entry["name"]]["real_status"] == "Completed":
    if status == "Completed":
        # if progress == 100 and status == "Done":
        color = "success"
        animated = False
        striped = False
        disabled = False
        # label = (
        #     f'{data_panoptes_custom_status[entry["name"]]["real_status"]} - {progress}'
        # )
    elif status in ["Too low nb of cells", "mm10 sample", "Non canonical plate"]:
        # elif progress == 100 and status in ["Missing report"]:
        # elif progress < 100 and status == "Error":
        color = "orange"
        animated = False
        striped = False
    elif status in ["Completed but status error"]:
        # elif progress == 100 and status in ["Completed but status error"]:
        # elif progress < 100 and status == "Error":
        color = "red"
        animated = False
        striped = False
    # elif progress < 100 and status == "Running":
    elif status in ["Running"]:
        # elif progress < 100:
        color = "primary"
        animated = True
        striped = True
        # label = f"{progress} %"
    elif status == "To process":
        # elif progress == 0 and status == "not_started":
        color = "grey"
        animated = False
        striped = False
        value = 0
        # print("TOTO")
        # label = "Not Started"
    # else:
    #     color = "grey"
    #     animated = False
    #     striped = False
    #     # print("TOTO")
    #     label = "Not Started"

    # run, sample = entry["name"].split("--")

    progress_bar = dbc.Progress(
        value=value,
        animated=animated,
        striped=striped,
        color=color,
        label=label,
        style={"height": "30px"},
    )

    return progress_bar


# def generate_progress_bar(entry):
#     status = entry["real_status"]
#     if status != "not_started":
#         progress = round((entry["jobs_done"] / entry["jobs_total"]) * 100, 2)
#     else:
#         progress = 0

#     color = "primary"
#     animated = True
#     striped = True
#     label = ""

#     label = f"{status} - {progress} %"

#     if status == "Completed":
#         progress = 100
#         color = "success"
#         animated = False
#         striped = False
#         disabled = False
#         label = "Completed"
#     elif "Report missing" in status or "Uncompleted execution" in status:
#         color = "orange"
#         animated = False
#         striped = False

#     elif "Error (to  investigate)" in status:
#         color = "danger"
#         animated = False
#         striped = False

#     # elif progress == 100 and status in ["Missing report", "Completed but status error"]:
#     #     # elif progress < 100 and status == "Error":
#     #     color = "orange"
#     #     animated = False
#     #     striped = False
#     # # elif progress < 100 and status == "Running":
#     elif progress < 100 and status == "Running" or status == "Error":
#         color = "primary"
#         animated = True
#         striped = True
#         label = f"{progress} %"
#     elif progress == 0 and status == "not_started":
#         color = "grey"
#         animated = False
#         striped = False
#         # print("TOTO")
#         label = "Not Started"

#     # run, sample = entry["name"].split("--")

#     progress_bar = dbc.Progress(
#         value=progress,
#         animated=animated,
#         striped=striped,
#         color=color,
#         label=label,
#         style={"height": "30px"},
#     )

#     return progress_bar


@app.callback(
    Output("progress-container-landing-page", "children"),
    Output("stored-refresh-button", "data"),
    Input("stored-progress", "data"),
    Input("url", "pathname"),
    Input("run-dropdown", "value"),
    Input("sample-dropdown", "value"),
    Input("refresh-button", "n_clicks"),
    State("stored-refresh-button", "data"),
)
def update_progress(
    data_panoptes_raw, url, selected_run, selected_sample, n_clicks, stored_n_clicks
):
    # print("UPDATE PROGRESS")
    # print(n_clicks, stored_n_clicks)
    continue_update = False
    if url != "/":
        raise dash.exceptions.PreventUpdate
        # return dash.no_update
    else:
        # print("UPDATE PROGRESS")
        # print(n_clicks, stored_n_clicks)
        if n_clicks is None:
            raise dash.exceptions.PreventUpdate
        else:
            if n_clicks == 0 and stored_n_clicks == 0:
                continue_update = True
            else:
                if n_clicks > stored_n_clicks:
                    continue_update = True
            if continue_update is True:
                # print("CONTINUE UPDATE")
                # print(n_clicks, stored_n_clicks)
                components = []

                data_panoptes = collections.OrderedDict(
                    sorted(data_panoptes_raw.items(), reverse=True)
                )
                # print("DATA PANOPTES")
                # print(data_panoptes)

                # Generate progress bars
                for entry in data_panoptes:
                    run, sample = entry.split("--")
                    process = True
                    if selected_run:
                        if run not in selected_run:
                            process = False
                    if selected_sample:
                        if sample not in selected_sample:
                            process = False
                    if process:
                        pipeline_progress = dict()
                        for pipeline in [
                            "ashleys-qc-pipeline",
                            # "mosaicatcher-pipeline",
                        ]:
                            pipeline_progress[pipeline] = generate_progress_bar(
                                data_panoptes[entry][pipeline]
                            )

                        row = dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dmc.Text(
                                            run,
                                            size="lg",
                                            weight=400,
                                        ),
                                    ],
                                    width=4,
                                ),
                                dbc.Col(
                                    [
                                        dcc.Link(
                                            [
                                                dmc.Text(
                                                    sample,
                                                    size="lg",
                                                    weight=400,
                                                )
                                            ],
                                            href=f"/{run}/{sample}",
                                            style={
                                                "color": "black",
                                                "text-decoration": "none",
                                            },
                                        ),
                                    ],
                                    width=4,
                                ),
                                dbc.Col(
                                    pipeline_progress["ashleys-qc-pipeline"],
                                    width=4,
                                ),
                                # dbc.Col(
                                #     pipeline_progress["mosaicatcher-pipeline"],
                                #     width=3,
                                # ),
                            ],
                            style={"height": "40px"},
                        )

                        components.append(row)
                return components, n_clicks


# print("UPDATE PROGRESS")
# print(n_clicks, stored_n_clicks)
# continue_update = False
# if url != "/":
#     raise dash.exceptions.PreventUpdate
#     # return dash.no_update
# else:
#     print("UPDATE PROGRESS")
#     print(n_clicks, stored_n_clicks)
#     if n_clicks is None:
#         raise dash.exceptions.PreventUpdate
#     else:
#         if n_clicks == 0 and stored_n_clicks == 0:
#             continue_update = True
#         else:
#             if n_clicks > stored_n_clicks:
#                 continue_update = True
#         if continue_update is True:
#             print("CONTINUE UPDATE")
#             print(n_clicks, stored_n_clicks)
#             components = []

#             data_panoptes = collections.OrderedDict(
#                 sorted(data_panoptes_raw.items(), reverse=True)
#             )
#             print("DATA PANOPTES")
#             print(data_panoptes)

#             # Generate progress bars
#             data_panoptes = custom_status()
#             if selected_run:
#                 data_panoptes = data_panoptes.loc[
#                     data_panoptes["run"].isin(selected_run)
#                 ]
#             if selected_sample:
#                 data_panoptes = data_panoptes.loc[
#                     data_panoptes["sample"].isin(selected_sample)
#                 ]

#             # data_panoptes = data_panoptes.loc[
#             #     (data_panoptes["run"].isin(selected_run))
#             #     & (data_panoptes["sample"].isin(selected_sample))
#             # ]

#             data, timestamp = fetch_data()
#             print("DATA")
#             print(data)

#             for run, samples in sorted(data.items(), reverse=True):
#                 for sample in samples:
#                     pipeline_progress = dict()

#                     for pipeline in [
#                         "ashleys-qc-pipeline",
#                         "mosaicatcher-pipeline",
#                     ]:
#                         tmp_df = data_panoptes.loc[
#                             (data_panoptes["run"] == run)
#                             & (data_panoptes["sample"] == sample)
#                             # & (data_panoptes["pipeline"] == pipeline)
#                         ]
#                         print(run, sample, pipeline)

#                         print(tmp_df)
#                         if pipeline in tmp_df.pipeline.values.tolist():
#                             for j, entry in tmp_df.iterrows():
#                                 run = entry["run"]
#                                 sample = entry["sample"]

#                                 if pipeline == entry["pipeline"]:
#                                     pipeline_progress[
#                                         pipeline
#                                     ] = generate_progress_bar(entry)
#                         else:
#                             pipeline_progress[pipeline] = generate_progress_bar(
#                                 {"real_status": "not_started"}
#                             )

#                     print(pipeline_progress)

#                     row = dbc.Row(
#                         [
#                             dbc.Col(
#                                 [
#                                     dmc.Text(
#                                         run,
#                                         size="lg",
#                                         weight=400,
#                                     ),
#                                 ],
#                                 width=3,
#                             ),
#                             dbc.Col(
#                                 [
#                                     dcc.Link(
#                                         [
#                                             dmc.Text(
#                                                 sample,
#                                                 size="lg",
#                                                 weight=400,
#                                             )
#                                         ],
#                                         href=f"/{run}/{sample}",
#                                         style={
#                                             "color": "black",
#                                             "text-decoration": "none",
#                                         },
#                                     ),
#                                 ],
#                                 width=3,
#                             ),
#                             dbc.Col(
#                                 pipeline_progress["ashleys-qc-pipeline"],
#                                 width=3,
#                             ),
#                             dbc.Col(
#                                 pipeline_progress["mosaicatcher-pipeline"],
#                                 width=3,
#                             ),
#                         ],
#                         style={"height": "40px"},
#                     )

#                     components.append(row)
#             return components, n_clicks


@app.callback(
    Output("stored-progress", "data"),
    Output("timestamp-progress", "children"),
    Input("url", "pathname"),
    State("stored-progress", "data"),
)
def update_progress(url, progress_store):
    # Fetch processed data from FastAPI service
    FASTAPI_HOST = config["fastapi"]["host"]
    FASTAPI_PORT = config["fastapi"]["port"]
    response = requests.get(f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/get-progress")

    response_json_complete = response.json()
    response_json = response_json_complete[0]
    timestamp_progress = response_json_complete[1]
    print("timestamp_progress")
    print(timestamp_progress)

    pd.options.display.max_rows = 200
    pd.options.display.max_colwidth = 30
    message_df = pd.read_json(StringIO(response_json), orient="records")
    print(message_df)

    # print(response_json)
    # print(timestamp_progress)
    # print(progress_store)
    # if not response_json:
    #     # return dash.no_update
    #     raise dash.exceptions.PreventUpdate

    # print("\n\n")
    # Extract data

    # tmp_data, timestamp = fetch_data()
    # data_lite = [
    #     f"{k}--{e}" for k, v in tmp_data.items() for e in sorted(v, reverse=False)
    # ]

    # # print("data_panoptes_raw")
    # # print(message_df)
    # # print(tmp_data)
    # # exit()
    # print([wf for wf in response_json["workflows"]])
    # data_panoptes_raw = [
    #     wf
    #     for wf in response_json["workflows"]
    #     if "--".join(wf["name"].split("--")[1:]) in data_lite
    # ]
    # print(data_panoptes_raw)

    # print("data_panoptes")

    data_panoptes = collections.defaultdict(dict)
    # for wf in data_panoptes_raw:
    #     pipeline, run, sample = wf["name"].split("--")
    #     data_panoptes[f"{run}--{sample}"][pipeline] = wf

    # data_panoptes = {wf["name"]: wf for wf in data_panoptes}

    for j, row in message_df.iterrows():
        # for pipeline in ["ashleys-qc-pipeline"]:
        # for pipeline in ["ashleys-qc-pipeline", "mosaicatcher-pipeline"]:
        # if pipeline not in data_panoptes[run_sample]:
        run_sample = f"{row['plate']}--{row['sample']}"
        data_panoptes[run_sample]["ashleys-qc-pipeline"] = {
            "name": f"ashleys-qc-pipeline--{run_sample}",
            # "jobs_total": 0,
            # "jobs_done": 0,
            # "status": "To process",
            "status": row["status"],
        }
    # if progress_store == data_panoptes:
    #     print("NO UPDATE")
    #     return dash.no_update
    # progress_store = data_panoptes

    # FASTAPI_HOST = config["fastapi"]["host"]
    # FASTAPI_PORT = config["fastapi"]["port"]
    # response = requests.get(f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/get-data")
    # response_json_complete = response.json()
    # response_json = response_json_complete[0]
    # timestamp_data = response_json_complete[1]
    print("timestamp_data")
    # timestamp_data = dmc.Text(f"Last data update: {timestamp}", size="xs")
    timestamp_progress = dmc.Text(
        f"Last progress update: {timestamp_progress}", size="xs"
    )
    div_timestamps = html.Div([timestamp_progress])
    print(div_timestamps)
    return data_panoptes, div_timestamps


@app.callback(
    Output({"type": "ashleys-run-progress-container", "index": MATCH}, "children"),
    Input("url", "pathname"),
    State("stored-progress", "data"),
)
def update_progress(url, progress_store):
    if url == "/":
        return dash.no_update
    else:
        run, sample = url.split("/")[1:3]

        if progress_store != {}:
            print("PROGRESS STORE")
            print(progress_store)
            progress_bar = generate_progress_bar(
                progress_store[f"{run}--{sample}"]["ashleys-qc-pipeline"]
            )

        else:
            progress_bar = generate_progress_bar({"status": "not_started"})
        return progress_bar


# @app.callback(
#     Output({"type": "mosaicatcher-run-progress-container", "index": MATCH}, "children"),
#     Input("url", "pathname"),
#     State("stored-progress", "data"),
# )
# def update_progress(url, progress_store):
#     if url == "/":
#         return dash.no_update
#     else:
#         run, sample = url.split("/")[1:3]
#         # print("\n\n")
#         # print(progress_store)
#         # print("\n\n")

#         if progress_store != {}:
#             progress_bar = generate_progress_bar(
#                 progress_store[f"{run}--{sample}"]["mosaicatcher-pipeline"]
#             )

#         else:
#             progress_bar = generate_progress_bar({"status": "not_started"})
#         return progress_bar


def violinplot_context(run, sample):
    df = load_data_for_vizu()

    if run in df.depictio_run_id.unique() and sample in df["sample"].unique():
        # Check if the figure exists in Redis
        fig_name = "violin_fig"
        if redis_client.exists(fig_name):
            # print("Figure exists in Redis")

            # Get the figure from Redis
            retrieved_figure_json = redis_client.get(fig_name)

            # Deserialize the JSON back to a Plotly figure
            # Since Redis returns data in bytes, we need to convert it to a string
            retrieved_figure_json = retrieved_figure_json.decode("utf-8")
            fig = plotly.io.from_json(retrieved_figure_json)

        else:
            # print("Figure does not exist in Redis")

            # Create a Plotly figure
            # figure = px.scatter(x=[0, 1, 2, 3, 4], y=[0, 1, 4, 9, 16])

            fig = px.box(
                df,
                x="sample",
                y="good",
                color="depictio_run_id",
                # facet_col="year",
                height=1000,
                hover_data=["depictio_run_id", "sample", "cell", "good"],
                points="all",
                boxmode="overlay",
            )

            # Serialize the figure to JSON
            figure_json = plotly.io.to_json(fig)

            # Store the figure in Redis
            # Assuming the key for storing the figure is 'my_figure'
            redis_client.set(fig_name, figure_json, ex=60)

        highlight_sample_position = df["sample"].unique().tolist().index(sample)

        fig.add_vline(
            x=highlight_sample_position,
            line_width=3,
            line_dash="dash",
            line_color="red",
        )
        fig.update_layout(yaxis_range=[0, 2e6])

        figure = dcc.Graph(figure=fig, style={"height": "50vh"})
        return figure

    else:
        return "No data available yet for this run/sample combination"


def bar_dupl(run, sample):
    df = load_data_for_vizu()
    if run in df.depictio_run_id.unique() and sample in df["sample"].unique():
        # Check if the figure exists in Redis
        fig_name = f"bar_dup_fig_{run}_{sample}"
        if redis_client.exists(fig_name):
            # print("Figure exists in Redis")

            # Get the figure from Redis
            retrieved_figure_json = redis_client.get(fig_name)

            # Deserialize the JSON back to a Plotly figure
            # Since Redis returns data in bytes, we need to convert it to a string
            retrieved_figure_json = retrieved_figure_json.decode("utf-8")
            fig = plotly.io.from_json(retrieved_figure_json)

        else:
            # print("Figure does not exist in Redis")

            # Create a Plotly figure
            # figure = px.scatter(x=[0, 1, 2, 3, 4], y=[0, 1, 4, 9, 16])

            fig = px.bar(
                df.loc[df["sample"] == sample].sort_values(by="cell"),
                x="cell",
                y="dupl",
                color="prediction",
                color_discrete_sequence=["red", "green"],
                # facet_col="year",
                hover_data=["depictio_run_id", "sample", "cell", "good", "dupl"],
                # points="all",
            )

            fig.update_layout(xaxis_categoryorder="category ascending")

            # Serialize the figure to JSON
            figure_json = plotly.io.to_json(fig)

            # Store the figure in Redis
            # Assuming the key for storing the figure is 'my_figure'
            redis_client.set(fig_name, figure_json, ex=60)

        figure = dcc.Graph(figure=fig, style={"height": "50vh"})
        # figure = dcc.Graph(figure=fig, style={"width": "50vh", "height": "50vh"})
        return figure

    else:
        return "No data available yet for this run/sample combination"


def cell_distribution(run, sample):
    df = load_data_for_vizu()
    if run in df.depictio_run_id.unique() and sample in df["sample"].unique():
        # Check if the figure exists in Redis
        fig_name = f"scatter_fig_{run}_{sample}"
        if redis_client.exists(fig_name):
            # print("Figure exists in Redis")

            # Get the figure from Redis
            retrieved_figure_json = redis_client.get(fig_name)

            # Deserialize the JSON back to a Plotly figure
            # Since Redis returns data in bytes, we need to convert it to a string
            retrieved_figure_json = retrieved_figure_json.decode("utf-8")
            fig = plotly.io.from_json(retrieved_figure_json)

        else:
            # print("Figure does not exist in Redis")

            # Create a Plotly figure
            # figure = px.scatter(x=[0, 1, 2, 3, 4], y=[0, 1, 4, 9, 16])

            fig = px.scatter(
                df.loc[df["sample"] == sample].sort_values(by="cell"),
                x="cell",
                y="good",
                color="prediction",
                color_discrete_sequence=["red", "green"],
                # facet_col="year",
                hover_data=[
                    "depictio_run_id",
                    "sample",
                    "cell",
                    "mapped",
                    "dupl",
                    "good",
                ],
            )

            fig.update_layout(
                yaxis_type="log", xaxis_categoryorder="category ascending"
            )
            fig.update_traces(marker=dict(size=10))  # Change 12 to your desired size

            # Serialize the figure to JSON
            figure_json = plotly.io.to_json(fig)

            # Store the figure in Redis
            # Assuming the key for storing the figure is 'my_figure'
            redis_client.set(fig_name, figure_json, ex=60)

        # highlight_sample_position = df["sample"].unique().tolist().index(sample)

        # fig.add_vline(
        #     x=highlight_sample_position,
        #     line_width=3,
        #     line_dash="dash",
        #     line_color="red",
        # )

        figure = dcc.Graph(figure=fig, style={"height": "50vh"})
        # figure = dcc.Graph(figure=fig, style={"width": "50vh", "height": "50vh"})
        return figure
    else:
        return "No data available yet for this run/sample combination"


@app.callback(
    Output({"type": "metadata-container", "index": MATCH}, "children"),
    [
        # Input("sample-dropdown", "value"),
        # Input("run-dropdown", "value"),
        Input("url", "pathname"),
        Input({"type": "homepage-button", "index": MATCH}, "n_clicks"),
    ],
    [State("stored-progress", "data")],
    # prevent_initial_call=True,
)
def fill_metadata_container(url, n_clicks, progress_store):
    if url == "/":
        raise dash.exceptions.PreventUpdate
    else:
        run, sample = url.split("/")[1:3]
        # if progress_store != {}:
        #     ashleys_run_id = progress_store[f"{run}--{sample}"]["ashleys-qc-pipeline"]["id"]
        #     mosaicatcher_run_id = progress_store[f"{run}--{sample}"][
        #         "mosaicatcher-pipeline"
        #     ]["id"]

        # index = "PE20"
        year = run.split("-")[0]
        genecore_data_folder = config["data"]["genecore_data_folder"]
        complete_data_folder = config["data"]["complete_data_folder"]
        data_folder = config["data"]["data_folder"]
        genecore_filepath = f"{genecore_data_folder}/{year}/{run}"
        pipeline_processed_data_filepath = f"{complete_data_folder}/{run}/{sample}"

        backup_processed_data_filepath = f"{data_folder}/{run}/{sample}"

        metadata_dict = {
            "Sample name": sample,
            "Run name": run,
            # "Sequencing index": index,
            "Raw data location": genecore_filepath,
            "Pipeline complete data location": pipeline_processed_data_filepath,
            "Backup processed data location": backup_processed_data_filepath,
        }

        card = dmc.Card(
            [
                dbc.Row(
                    [
                        dbc.Col(dmc.Text(k, size="md", weight=500), width=4),
                        dbc.Col(dmc.Text(v, size="sm"), width="auto"),
                    ]
                )
                for k, v in metadata_dict.items()
            ]
        )

        # Later, when you need to retrieve the figure

        violin_plot = violinplot_context(run, sample)

        cell_distribution_plot = cell_distribution(run, sample)

        box_dupl_plot = bar_dupl(run, sample)

        row = dbc.Row(
            [
                dbc.Col(
                    [dmc.Title("Sample context", order=3), cell_distribution_plot],
                    width=6,
                ),
                dbc.Col(
                    [dmc.Title("Duplication level", order=3), box_dupl_plot], width=6
                ),
            ]
        )

        # figure = dcc.Graph(figure=px.scatter(x=[0, 1, 2, 3, 4], y=[0, 1, 4, 9, 16]))
        # export that figure into redis and then load it from redis

        # + [
        #     dbc.Row(
        #         [
        #             dbc.Col(
        #                 dmc.Text("Panoptes ashleys link", size="lg", weight=500),
        #                 width=4,
        #             ),
        #             dbc.Col(
        #                 dcc.Link(
        #                     "Panoptes",
        #                     href=f"http://localhost:8058/workflow/{ashleys_run_id}",
        #                     style={"color": "black", "text-decoration": "none"},
        #                 ),
        #                 width="auto",
        #             ),
        #         ]
        #     ),
        #     dbc.Row(
        #         [
        #             dbc.Col(
        #                 dmc.Text("Panoptes mosaicatcher link", size="lg", weight=500),
        #                 width=4,
        #             ),
        #             dbc.Col(
        #                 dcc.Link(
        #                     "Panoptes",
        #                     href=f"http://localhost:8058/workflow/{mosaicatcher_run_id}",
        #                     style={"color": "black", "text-decoration": "none"},
        #                 ),
        #                 width="auto",
        #             ),
        #         ]
        #     )
        # ]
        # )
        # print(card)

        return [
            card,
            html.Hr(),
            dmc.Title("Visualisation", order=2),
            dmc.Title("Global context", order=3),
            violin_plot,
            row,
            html.Hr(),
        ]


@app.callback(
    Output({"type": "invisible-output", "index": MATCH}, "data"),
    Input("url", "pathname"),
    Input({"type": "homepage-button", "index": MATCH}, "n_clicks"),
    Input({"type": "report-button-ashleys", "index": MATCH}, "n_clicks"),
    Input({"type": "run-mosaicatcher-button", "index": MATCH}, "n_clicks"),
    Input({"type": "report-button-mosaicatcher", "index": MATCH}, "n_clicks"),
    Input({"type": "save-button", "index": MATCH}, "n_clicks"),
    Input({"type": "stored-homepage-button", "index": MATCH}, "n_clicks"),
    State({"type": "stored-report-button-ashleys", "index": MATCH}, "data"),
    State({"type": "stored-run-mosaicatcher-button", "index": MATCH}, "data"),
    State({"type": "stored-report-button-mosaicatcher", "index": MATCH}, "data"),
    State({"type": "stored-save-button", "index": MATCH}, "data"),
    State({"type": "stored-selectedRows", "index": MATCH}, "data"),
)
def write_sample_state_to_json(
    url,
    homepage_button,
    report_button,
    run_mosaicatcher_button,
    report_mosaicatcher_button,
    save_button,
    stored_homepage_button,
    stored_report_button,
    stored_run_mosaicatcher_button,
    stored_report_mosaicatcher_button,
    stored_save_button,
    stored_selected_rows,
):
    if url == "/":
        raise dash.exceptions.PreventUpdate
    else:
        # print("\n\n")
        # print("WRITING TO JSON")
        # print(
        #     homepage_button,
        #     report_button,
        #     run_mosaicatcher_button,
        #     report_mosaicatcher_button,
        #     save_button,
        # )
        # print(
        #     stored_homepage_button,
        #     stored_report_button,
        #     stored_run_mosaicatcher_button,
        #     stored_report_mosaicatcher_button,
        #     stored_save_button,
        # )
        run, sample = url.split("/")[1:3]

        data_to_save = {
            "run": run,
            "sample": sample,
            "stored-homepage-button": stored_homepage_button,
            "stored-report-button-ashleys": stored_report_button,
            "stored-save-button": stored_save_button,
            "stored-run-mosaicatcher-button": stored_run_mosaicatcher_button,
            "stored-report-button-mosaicatcher": stored_report_mosaicatcher_button,
            "stored-selectedRows": stored_selected_rows,
        }

        # print(data_to_save)
        data_folder = config["data"]["data_folder"]
        os.makedirs(f"{data_folder}/{run}/{sample}/config", exist_ok=True)
        with open(f"{data_folder}/{run}/{sample}/config/strandscape.json", "w") as f:
            print("Writing to json")
            json.dump(data_to_save, f)
        # with open(f"backup/{run}--{sample}.json", "w") as f:
        #     json.dump(data_to_save, f)
        return None


@app.callback(
    Output({"type": "trigger-snakemake", "index": MATCH}, "children"),
    Output({"type": "stored-run-button", "index": MATCH}, "data"),
    Input({"type": "run-button", "index": MATCH}, "n_clicks"),
    Input("url", "pathname"),
    State({"type": "email-form", "index": ALL}, "value"),
    State({"type": "sv-calling-form", "index": ALL}, "value"),
    State({"type": "blacklisting-form", "index": ALL}, "checked"),
    State({"type": "stored-run-button", "index": MATCH}, "data"),
)
def trigger_snakemake(
    n,
    url,
    email,
    sv_calling,
    blacklisting,
    stored_run_button,
):
    print("\n\n")
    print(n, stored_run_button)
    if n > stored_run_button:
        run, sample = url.split("/")[1:3]

        print(f"EMAIL: {email}")
        print(f"SV CALLING: {sv_calling}")
        print(f"BLACKLISTING: {blacklisting}")

        email = email[0]

        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

        check_email = False
        if email:
            print(email, re.match(pattern, email))
            if re.match(pattern, email):
                check_email = True

        if check_email is False:
            return (
                html.Div(
                    [
                        # html.Hr(),
                        dmc.Center(
                            dmc.Text(
                                "Email not valid", color="red", weight=700, size="lg"
                            )
                        ),
                    ]
                ),
                n,
            )

        else:
            sv_calling = sv_calling[0]
            blacklisting = blacklisting[0]

            snake_args = {
                "email": email,
                "multistep_normalisation_for_SV_calling": (
                    True
                    if sv_calling == "multistep_normalisation_for_SV_calling"
                    else False
                ),
                "hgsvc_based_normalized_counts": (
                    True if sv_calling == "hgsvc_based_normalized_counts" else False
                ),
                "blacklisting": blacklisting,
            }
            snake_args["multistep_normalisation"] = True

            # Trigger the API endpoint
            pipeline = "mosaicatcher-pipeline"

            # Define the arguments you want to pass
            args = (pipeline, run, sample, snake_args)

            thread = threading.Thread(target=trigger_snakemake_api, args=args)
            thread.start()

            # response = requests.post(
            #     f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/trigger-snakemake/{pipeline}--{run}--{sample}",
            #     json=snake_args,
            # )

            # return (
            #     html.Div(id={"type": "email-validation-message", "index": f"{run}--{sample}"}),
            #     n,
            # )
            print("TRIGGERED", n)
            return (
                dbc.Modal(
                    [
                        dbc.ModalHeader(html.H2("Run MosaiCatcher")),
                        dbc.ModalBody(
                            [
                                html.Div(
                                    [
                                        dmc.Text(
                                            f"Your pipeline job has been successfully submitted for {run} - {sample}. \nYou will receive an email when the pipeline is completed.",
                                            size="lg",
                                        ),
                                    ]
                                ),
                            ]
                        ),
                    ],
                    id={
                        "type": "modal-success-mosaicatcher",
                        "index": f"{run}--{sample}",
                    },
                    size="lg",
                    is_open=True,
                    centered=True,
                    scrollable=True,
                    # style=CONTENT_STYLE,
                ),
                n,
            )

        # return f"{email}"
    else:
        raise dash.exceptions.PreventUpdate


@app.callback(
    Output({"type": "form-element", "index": MATCH}, "children"),
    Input("url", "pathname"),
    Input({"type": "run-mosaicatcher-button", "index": MATCH}, "n_clicks"),
)
def generate_form_element(selected_run, selected_sample):
    email_input = html.Div(
        [
            dmc.Title(
                "Other parameters",
                order=3,
                style={"paddingBottom": "20px", "paddingTop": "10px"},
            ),
            dbc.Card(
                [
                    dbc.Row(
                        [
                            dbc.Label(
                                "Email",
                                html_for={
                                    "type": f"email-{selected_run}-{selected_sample}"
                                },
                                width=2,
                            ),
                            dbc.Col(
                                [
                                    dbc.Input(
                                        type="email",
                                        # value="TEST@TEST.com",
                                        id={
                                            "type": "email-form",
                                            "index": f"{selected_run}--{selected_sample}",
                                        },
                                        placeholder="Enter email",
                                    ),
                                    dbc.FormText(
                                        "Specify your email address to be updated on the status of the pipeline",
                                        color="secondary",
                                    ),
                                ],
                                width=10,
                            ),
                        ],
                        className="mb-3",
                    ),
                ],
                className="p-2",
                style={"border": "1px solid grey", "padding": "10px 0px"},
            ),
        ]
    )

    sv_calling_input = html.Div(
        [
            dmc.Title(
                "SV calling",
                order=3,
                style={"paddingBottom": "20px", "paddingTop": "10px"},
            ),
            dbc.Card(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Label(
                                    "Norm Method",
                                    html_for={
                                        "type": "sv-calling-form",
                                        "index": f"{selected_run}--{selected_sample}",
                                    },
                                ),
                                width=2,
                            ),
                            dbc.Col(
                                [
                                    dmc.SegmentedControl(
                                        id={
                                            "type": f"sv-calling-form",
                                            "index": f"{selected_run}--{selected_sample}",
                                        },
                                        data=[
                                            {
                                                "label": "Multistep normalisation",
                                                "value": "multistep_normalisation_for_SV_calling",
                                            },
                                            {
                                                "label": "HGSVC normalisation",
                                                "value": "hgsvc_based_normalisation",
                                            },
                                        ],
                                        color="red",
                                        value="multistep_normalisation_for_SV_calling",
                                    ),
                                    html.Br(),
                                    dbc.FormText(
                                        "Rely on the multistep normalisation or the HGSVC normalisation applied to the counts file to be used for SV calling",
                                        color="secondary",
                                    ),
                                ],
                                width=10,
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Hr(),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Label(
                                    "Blacklisting",
                                    html_for={
                                        "type": f"blacklisting-form",
                                        "index": f"{selected_run}--{selected_sample}",
                                    },
                                ),
                                width=2,
                            ),
                            dbc.Col(
                                [
                                    dmc.Switch(
                                        id={
                                            "type": f"blacklisting-form",
                                            "index": f"{selected_run}--{selected_sample}",
                                        },
                                        checked=True,
                                        # color="blue",
                                        # label="multistep_normalisation_for_SV_calling",
                                        # thumbIcon=DashIconify(icon="bi:mask"),
                                        # size="lg",
                                        color="red",
                                    ),
                                    dbc.FormText(
                                        "Apply blacklisted regions to counts file",
                                        color="secondary",
                                    ),
                                ],
                                width=10,
                            ),
                        ],
                        className="mb-3",
                    ),
                ],
                className="p-2",
                style={"border": "1px solid grey", "padding": "10px 0px"},
            ),
        ]
    )

    downstream_analysis_input = [
        html.Div(
            [
                dmc.Title(
                    "Downstream analysis",
                    order=3,
                    style={"paddingBottom": "20px", "paddingTop": "10px"},
                ),
                dbc.Card(
                    [
                        dbc.Row(
                            [
                                dbc.Label(
                                    "Arbigent",
                                    html_for={
                                        "type": f"arbigent-form",
                                        "index": f"{selected_run}--{selected_sample}",
                                    },
                                    width=2,
                                ),
                                dbc.Col(
                                    [
                                        dmc.Switch(
                                            id={
                                                "type": f"arbigent-form",
                                                "index": f"{selected_run}--{selected_sample}",
                                            },
                                            # label="ArbiGent",
                                            checked=False,
                                            color="red",
                                        ),
                                        dbc.FormText(
                                            "Use ArbiGent (Arbitrary Genotyping) to genotype specific positions",
                                            color="secondary",
                                        ),
                                    ],
                                    width=10,
                                ),
                            ],
                        ),
                        html.Hr(),
                        dbc.Row(
                            [
                                dbc.Label(
                                    "ArbiGent BED file",
                                    html_for={
                                        "type": f"arbigent-bed-file-form",
                                        "index": f"{selected_run}--{selected_sample}",
                                    },
                                    width=2,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Input(
                                            id={
                                                "type": f"arbigent-bed-file-form",
                                                "index": f"{selected_run}--{selected_sample}",
                                            },
                                            placeholder="Please enter path for ArbiGent BED file",
                                            disabled=False,
                                            # color="blue",
                                        ),
                                        dbc.FormText(
                                            "ArbiGent BED file location on the cluster",
                                            color="secondary",
                                        ),
                                    ],
                                    width=10,
                                ),
                            ],
                        ),
                    ],
                    className="p-2",
                    style={"border": "1px solid grey", "padding": "10px 0px"},
                ),
            ]
        ),
    ]

    form = dbc.Form(
        [
            sv_calling_input,
            # html.Hr(),
            # *downstream_analysis_input,
            html.Hr(),
            email_input,
        ]
    )
    return form


# @app.callback(
#     Output({"type": "depictio-container", "index": MATCH}, "children"),
#     Input("url", "pathname"),
# )
# def generate_depictio_container(url):
#     if url == "/":
#         raise dash.exceptions.PreventUpdate
#     else:
#         run, sample = url.split("/")[1:3]
#         import plotly_express as px

#         df = px.data.iris()

#         tmp_data = fetch_data()

#         data_lite = [f"{k}--{e}" for k, v in tmp_data.items() for e in sorted(v)]
#         data_lite_index = data_lite.index(f"{run}--{sample}")
#         colors = ["red", "green", "blue"]
#         fig = px.scatter(
#             df,
#             x=df.columns[random.randint(0, len(df.columns))],
#             y=df.columns[random.randint(0, len(df.columns))],
#             hover_name=df.columns[data_lite_index],
#             color=df.columns[data_lite_index],
#             title=f"{run} - {sample}",
#         )

#         graph = dcc.Graph(
#             id={
#                 "type": "depictio-graph",
#                 "index": f"{run}--{sample}",
#             },
#             figure=fig,
#         )
#         return graph


@app.callback(
    [
        Output({"type": "run-sample-container", "index": MATCH}, "children"),
        Output({"type": "stored-homepage-button", "index": MATCH}, "data"),
        Output({"type": "stored-report-button-ashleys", "index": MATCH}, "data"),
        Output({"type": "stored-run-mosaicatcher-button", "index": MATCH}, "data"),
        Output({"type": "stored-report-button-mosaicatcher", "index": MATCH}, "data"),
    ],
    [
        Input({"type": "homepage-button", "index": MATCH}, "n_clicks"),
        Input({"type": "report-button-ashleys", "index": MATCH}, "n_clicks"),
        Input({"type": "run-mosaicatcher-button", "index": MATCH}, "n_clicks"),
        Input({"type": "report-button-mosaicatcher", "index": MATCH}, "n_clicks"),
        Input("url", "pathname"),
    ],
    [
        State({"type": "stored-homepage-button", "index": MATCH}, "data"),
        State({"type": "stored-report-button-ashleys", "index": MATCH}, "data"),
        State({"type": "stored-run-mosaicatcher-button", "index": MATCH}, "data"),
        State({"type": "stored-report-button-mosaicatcher", "index": MATCH}, "data"),
        State({"type": "stored-selectedRows", "index": MATCH}, "data"),
    ],
)
def populate_container_sample(
    n_clicks_homepage_button,
    n_clicks_report_ashleys_button,
    n_clicks_beldevere_button,
    n_clicks_report_mosaicatcher_button,
    url,
    report_homepage_button_stored,
    report_ashleys_button_stored,
    beldevere_button_stored,
    report_mosaicatcher_button_stored,
    selected_rows,
):
    if url == "/":
        raise dash.exceptions.PreventUpdate
    else:
        selected_run, selected_sample = url.split("/")[1:3]
        print(
            n_clicks_homepage_button,
            n_clicks_report_ashleys_button,
            n_clicks_beldevere_button,
        )
        print(
            report_homepage_button_stored,
            report_ashleys_button_stored,
            beldevere_button_stored,
        )

        index = "PE20"
        genecore_filepath = (
            f"/g/korbel/STOCKS/Data/Assay/sequencing/2023/{selected_run}"
        )
        pipeline_processed_data_filepath = f"/scratch/tweber/DATA/MC_DATA/STOCKS/Sequencing/{selected_run}/{selected_sample}"
        backup_processed_data_filepath = (
            f"/g/korbel/WORKFLOW_RESULTS/{selected_run}/{selected_sample}"
        )

        metadata_dict = {
            "Sample name": selected_sample,
            "Run name": selected_run,
            "Sequencing index": index,
            "Raw data location": genecore_filepath,
            "Pipeline processed data location": pipeline_processed_data_filepath,
            "Backup processed data location": backup_processed_data_filepath,
        }

        card = dmc.Card(
            [
                dbc.Row(
                    [
                        dbc.Col(dmc.Text(k, size="lg", weight=500), width=4),
                        dbc.Col(dmc.Text(v, size="md"), width="auto"),
                    ]
                )
                for k, v in metadata_dict.items()
            ],
            id={
                "type": "metadata-container",
                "index": f"{selected_run}--{selected_sample}",
            },
        )

        depictio = html.Div(
            id={
                "type": "depictio-container",
                "index": f"{selected_run}--{selected_sample}",
            },
        )

        homepage_layout = html.Div(
            children=[
                # html.Hr(),
                # dmc.Title(
                #     f"Depictio",
                #     order=2,
                #     style={"paddingTop": "20px", "paddingBottom": "20px"},
                # ),
                # depictio,
                # html.Hr(),
                dmc.Title(
                    "Ashleys-QC run",
                    order=2,
                    style={"paddingTop": "20px", "paddingBottom": "20px"},
                ),
                html.Div(
                    id={
                        "type": "ashleys-run-progress-container",
                        "index": f"{selected_run}--{selected_sample}",
                    },
                ),
                # html.Hr(),
                # dmc.Title(
                #     "MosaiCatcher run",
                #     order=2,
                #     style={"paddingTop": "20px", "paddingBottom": "20px"},
                # ),
                # html.Div(
                #     id={
                #         "type": "mosaicatcher-run-progress-container",
                #         "index": f"{selected_run}--{selected_sample}",
                #     },
                # ),
                html.Hr(),
                dmc.Title(
                    f"{selected_sample} metadata",
                    order=2,
                    style={"paddingTop": "20px", "paddingBottom": "20px"},
                ),
                dbc.Spinner(
                    children=[card], spinner_style={"width": "3rem", "height": "3rem"}
                ),
            ]
        )

        if (
            n_clicks_homepage_button
            and n_clicks_homepage_button > report_homepage_button_stored
        ):
            return (
                homepage_layout,
                n_clicks_homepage_button,
                n_clicks_report_ashleys_button,
                n_clicks_beldevere_button,
                n_clicks_report_mosaicatcher_button,
                # progress_store,
            )

        # Check which button was clicked last by comparing their timestamps
        elif (
            n_clicks_report_ashleys_button
            and n_clicks_report_ashleys_button > report_ashleys_button_stored
        ):
            pipeline = "mosaicatcher-pipeline"
            FASTAPI_HOST = config["fastapi"]["host"]
            FASTAPI_PORT = config["fastapi"]["port"]
            iframe = [
                html.Iframe(
                    src=f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/reports/{selected_run}--{selected_sample}/{pipeline}/report.html",
                    style={"width": "100%", "height": "900px"},
                )
            ]
            return (
                iframe,
                n_clicks_homepage_button,
                n_clicks_report_ashleys_button,
                n_clicks_beldevere_button,
                n_clicks_report_mosaicatcher_button,
            )

        elif (
            n_clicks_report_mosaicatcher_button
            and n_clicks_report_mosaicatcher_button > report_mosaicatcher_button_stored
        ):
            pipeline = "mosaicatcher-pipeline"
            FASTAPI_HOST = config["fastapi"]["host"]
            FASTAPI_PORT = config["fastapi"]["port"]
            print(
                f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/reports/{selected_run}--{selected_sample}/{pipeline}/report.html"
            )
            iframe = [
                html.Iframe(
                    src=f"http://{FASTAPI_HOST}:{FASTAPI_PORT}/reports/{selected_run}--{selected_sample}/{pipeline}/report.html",
                    style={"width": "100%", "height": "900px"},
                )
            ]
            return (
                iframe,
                n_clicks_homepage_button,
                n_clicks_report_ashleys_button,
                n_clicks_beldevere_button,
                n_clicks_report_mosaicatcher_button,
            )
        elif (
            n_clicks_beldevere_button
            and n_clicks_beldevere_button > beldevere_button_stored
        ):
            form_element = generate_form_element(selected_run, selected_sample)
            print(form_element)
            x = len(selected_rows)
            color_x = "red"
            if x > 0 and x < 10:
                color_x = "red"
            elif x >= 10 and x < 50:
                color_x = "orange"
            elif x >= 50:
                color_x = "green"

            belvedere_layout = html.Div(
                [
                    dbc.Container(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dmc.Card(
                                                children=[
                                                    dmc.CardSection(
                                                        [
                                                            dmc.Group(
                                                                children=[
                                                                    DashIconify(
                                                                        icon="ooui:logo-wikimedia-discovery",
                                                                        width=40,
                                                                    ),
                                                                    dmc.Title(
                                                                        f"Run MosaiCatcher on {selected_sample}",
                                                                        order=2,
                                                                    ),
                                                                    # dmc.Br(),
                                                                    dmc.Center(
                                                                        dmc.Text(
                                                                            f"{x} cells will be processed",
                                                                            color=color_x,
                                                                            weight=500,
                                                                            size="md",
                                                                        )
                                                                    ),
                                                                ],
                                                                position="left",
                                                            ),
                                                        ],
                                                        withBorder=True,
                                                        inheritPadding=True,
                                                        py="xs",
                                                    ),
                                                ]
                                            ),
                                            html.Hr(),
                                            html.Div(
                                                id={
                                                    "type": "form-element",
                                                    "index": f"{selected_run}--{selected_sample}",
                                                }
                                            ),
                                            # form_element,
                                        ],
                                        width=6,
                                        className="mx-auto",
                                    ),  # Adjusted alignment
                                ]
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dmc.Center(
                                            children=[
                                                dcc.Store(
                                                    id={
                                                        "type": "stored-run-button",
                                                        "index": f"{selected_run}--{selected_sample}",
                                                    },
                                                    data=0,
                                                ),
                                                dmc.Button(
                                                    "Run MosaiCatcher",
                                                    id={
                                                        "type": "run-button",
                                                        "index": f"{selected_run}--{selected_sample}",
                                                    },
                                                    color="red",
                                                    variant="filled",
                                                    disabled=False,
                                                    n_clicks=0,
                                                    className="mt-3",
                                                    style={
                                                        "width": "auto",
                                                        "display": "none",
                                                    },
                                                    size="xl",
                                                    radius="xl",
                                                    leftIcon=DashIconify(
                                                        icon="zondicons:play-outline"
                                                    ),
                                                ),
                                            ]
                                        ),
                                        width=6,
                                        className="mx-auto",  # Adjusted button alignment
                                    ),
                                ]
                            ),
                            dbc.Row(
                                html.Div(
                                    id={
                                        "type": "trigger-snakemake",
                                        "index": f"{selected_run}--{selected_sample}",
                                    }
                                ),
                            ),
                        ],
                        fluid=False,
                    ),
                ],
                style={"height": "100vh"},
            )
            return (
                belvedere_layout,
                n_clicks_homepage_button,
                n_clicks_report_ashleys_button,
                n_clicks_beldevere_button,
                n_clicks_report_mosaicatcher_button,
            )
        else:
            return (
                homepage_layout,
                n_clicks_homepage_button,
                n_clicks_report_ashleys_button,
                n_clicks_beldevere_button,
                n_clicks_report_mosaicatcher_button,
            )


@app.callback(
    Output("sidebar-stats", "children"),
    Input("url", "pathname"),
)
def generate_sidebar_stats(url):
    if url:
        print("\n\n")
        print("generating sidebar stats")
        # data, timestamp = fetch_data()
        data = load_data_from_file(file_path="strandscape_vizu_dev.parquet")
        data = data.loc[data["depictio_run_id"].str.contains("2023|2024", regex=True)]
        print(data)
        # print(data)

        nb_runs = data.depictio_run_id.nunique()
        nb_samples = data[["depictio_run_id", "sample"]].drop_duplicates().shape[0]
        nb_cells = data.shape[0]
        # print(nb_runs)
        # nb_samples = sum([len(v) for k, v in data.items()])
        # print(nb_samples)
        layout = [
            dmc.Center(
                [
                    dmc.Text(
                        f"Runs: {nb_runs}",
                        size="sm",
                        weight=400,
                    ),
                ],
            ),
            dmc.Center(
                dmc.Text(
                    f"Samples: {nb_samples}",
                    size="sm",
                    weight=400,
                ),
            ),
            dmc.Center(
                dmc.Text(
                    f"Cells: {nb_cells}",
                    size="sm",
                    weight=400,
                ),
            ),
        ]
        print(layout)
        return layout


sidebar = html.Div(
    [
        dbc.Row(
            [
                dbc.Col(DashIconify(icon="noto:dna", width=30), width=2),
                dbc.Col(
                    dcc.Link(
                        children=[dmc.Title("Strand-Scape", order=2)],
                        href="/",
                        style={
                            "text-decoration": "none",  # Remove the underline from the link
                            "color": "inherit",  # Use the default text color (or any color you prefer)
                        },
                    ),
                ),
            ]
        ),
        html.Hr(),
        dmc.Center(
            dmc.Text(
                "Welcome to Strand-Scape!",
                size="lg",
                weight=500,
            )
        ),
        html.Hr(),
        dbc.Spinner(html.Div(id="sidebar-stats")),
        # dmc.Center(
        #     dbc.Row(
        #         [
        #             dbc.Col(DashIconify(icon="mdi:eiffel-tower", width=20), width=1),
        #             # dbc.Col(dmc.Title("Belvedere", order=4)),
        #         ]
        #     )
        # ),
        # html.Hr(),
        html.Div(
            id="timestamp-progress",
            style={"position": "absolute", "bottom": "0", "width": "100%"},
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(
                    html.H1("Warning!", className="text-warning"), id="modal-header"
                ),
                dbc.ModalBody(
                    html.H5(id="modal-body", className="text-warning"),
                    # style={"background-color": "#F0FFF0"},
                ),
                dbc.ModalFooter(
                    dbc.Button(
                        "Close",
                        id="modal-close",
                        className="ml-auto",
                        color="warning",
                    )
                ),
            ],
            id="warning-modal",
            centered=True,
            is_open=False,  # initially closed
        ),
    ],
    style=SIDEBAR_STYLE,
)

general_backend_components = html.Div(
    [
        dcc.Store(
            id="stored-progress",
            storage_type="session",
            data={},
        ),
        # dcc.Interval(id="interval", interval=20000, n_intervals=0),
        # dcc.Interval(id="interval-progress", interval=20000, n_intervals=0),
        dcc.Location(id="url", refresh=False),
    ]
)


main_content = html.Div(
    [
        html.Div(
            id="output-container",
            style=CONTENT_STYLE,
        ),
    ]
)

app.layout = html.Div(
    [
        general_backend_components,
        # navbar,
        sidebar,
        main_content,
        # dash.page_container,
    ]
)


if __name__ == "__main__":
    app.run_server(debug=True, host=config["dash"]["host"], port=config["dash"]["port"])
