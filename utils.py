import collections
import pandas as pd
import os, sys
import yaml
import dash_bootstrap_components as dbc
from dash import dcc, html
import re
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import requests
import json

def merge_labels_and_info(labels, info):
    labels_df = pd.read_csv(labels, sep="\t")
    labels_df["cell"] = labels_df["cell"].str.replace(".sort.mdup.bam", "")
    info_df = pd.read_csv(info, sep="\t", skiprows=13)
    # info_df["pass1"] = info_df["pass1"].astype(bool)
    merge_df = pd.merge(labels_df, info_df, on=["sample", "cell"])[
        ["cell", "probability", "prediction", "pass1", "good", "mapped", "dupl"]
    ]
    # print(labels_df)
    # print(info_df)
    return merge_df


def get_files_structure(root_folder):
    data_dict = collections.defaultdict(list)
    for run_name_folder in os.listdir(root_folder):
        run_name = run_name_folder
        for sample_folder in os.listdir(os.path.join(root_folder, run_name_folder)):
            sample_name = sample_folder
            data_dict[run_name].append(sample_name)

    return data_dict


# Belvedere
def generate_form_element(selected_run, selected_sample):
    # if meta["type"] == "bool":
    #     input_element = (
    #         dbc.Checklist(
    #             id=id,
    #             options=[{"label": "", "value": 1}],
    #             inline=True,
    #             switch=True,
    #             value=[1],
    #         )
    #         if meta["type"] == "bool"
    #         else dbc.Input(id=id, type=meta["type"])
    #     )

    # else:
    #     input_element = dbc.Input(
    #         id=id, type="text", value=meta.get("default", ""), className="m-0 p-0"
    #     )

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
                                        value="TEST@TEST.com",
                                        id={
                                            "type": f"email-{selected_run}-{selected_sample}"
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
                                        "type": f"sv_calling-{selected_run}-{selected_sample}"
                                    },
                                ),
                                width=2,
                            ),
                            dbc.Col(
                                [
                                    dmc.SegmentedControl(
                                        id={
                                            "type": f"sv_calling-{selected_run}-{selected_sample}"
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
                                        "type": f"blacklisting-{selected_run}-{selected_sample}"
                                    },
                                ),
                                width=2,
                            ),
                            dbc.Col(
                                [
                                    dmc.Switch(
                                        id={
                                            "type": f"blacklisting-{selected_run}-{selected_sample}"
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
                                        "type": f"arbigent-{selected_run}-{selected_sample}"
                                    },
                                    width=2,
                                ),
                                dbc.Col(
                                    [
                                        dmc.Switch(
                                            id={
                                                "type": f"arbigent-{selected_run}-{selected_sample}"
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
                                        "type": f"arbigent_bed_file-{selected_run}-{selected_sample}"
                                    },
                                    width=2,
                                ),
                                dbc.Col(
                                    [
                                        dbc.Input(
                                            id={
                                                "type": f"arbigent_bed_file-{selected_run}-{selected_sample}"
                                            },
                                            placeholder="Please enter path for ArbiGent BED file",
                                            disabled=False
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
            html.Hr(),
            *downstream_analysis_input,
            html.Hr(),
            email_input,
        ]
    )
    return form

    # return html.Div(
    #     [
    #         dbc.Card(
    #             [
    #                 html.Div(
    #                     [
    #                         html.Label(
    #                             id,
    #                             className="font-weight-bold text-white p-2",
    #                             style={
    #                                 "backgroundColor": "#6c757d",
    #                                 "marginLeft": "0px",
    #                             },
    #                         ),
    #                         html.Div(
    #                             [input_element],
    #                             style={
    #                                 "display": "inline-block",
    #                                 "verticalAlign": "middle",
    #                                 "marginLeft": "20px",
    #                             },
    #                         ),
    #                     ],
    #                     style={"display": "flex", "alignItems": "center"},
    #                 ),
    #             ],
    #             className="p-2",
    #             style={"border": "1px solid grey", "padding": "10px 0px"},
    #         ),
    #         html.Small(meta["desc"], className="text-muted"),
    #     ],
    #     className="mb-2",
    # )


# TODO: headerTooltip
columnDefs = [
    {
        "field": "cell",
        "checkboxSelection": True,
        "headerCheckboxSelection": True,
        "minWidth": 250,
    },
    # {"field": "sample", "minWidth": 200},
    {
        "headerName": "Ashleys-QCMosaiCatcher counts",
        "children": [
            {"field": "probability", "minWidth": 150},
            {"field": "prediction"},
        ],
    },
    {
        "headerName": "MosaiCatcher counts",
        "children": [
            {"field": "pass1", "maxWidth": 120},
            {"field": "good", "minWidth": 150},
            {"field": "mapped"},
            {"field": "dupl"},
        ],
    },
]


defaultColDef = {
    "flex": 1,
    "minWidth": 150,
    "sortable": True,
    "resizable": True,
    "filter": True,
    "editable": True,
}


SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "18rem",
    "padding": "2rem 1rem",
    "background-color": "#f8f9fa",
}

CONTENT_STYLE = {
    "margin-left": "20rem",
    "margin-right": "2rem",
    "padding": "2rem 1rem",
}
CONTENT_STYLE = {
    "margin-left": "20rem",
    "margin-right": "2rem",
    "padding": "2rem 1rem",
}


# BELVEDERE

# # Load the metadata
# with open("config.yaml", "r") as stream:
#     try:
#         category_metadata = yaml.safe_load(stream)
#     except yaml.YAMLError as exc:
#         print(exc)
#         category_metadata = {}


# Define the categories for grouping the parameters


# Group parameters by category (for simplicity, we will categorize based on the initial character)
# categories = list(category_metadata.keys())
# print(categories)


# PROGRESS

LOGS_DIR = "logs_mosaicatcher/selected_logs/"
pattern = re.compile(r"\d+ of \d+ steps \(\d+%\) done")


def get_progress_from_file(file_path):
    with open(file_path, "r") as f:
        log_content = f.read()
    log_lines = [e for e in log_content.strip().split("\n") if pattern.match(e)][-1]
    # for line in log_lines:
    #     if pattern.match(line):
    # print(log_lines)
    progress = int(re.search(r"\((\d+)%\)", log_lines).group(1))
    # print(progress)
    return progress

def get_progress_from_api(run, sample):

    url = "http://127.0.0.1:8053/api/workflows"
    response_json = requests.get(url, headers={"Accept": "application/json"}).json()
    print(response_json)
    data = [wf for wf in response_json["workflows"] if wf["name"] == f"{run}-{sample}"]
    data = data[0] if data else {}
    print(data)
    if not data:
        data = {"name" : f"{run}-{sample}", "jobs_total": 0, "jobs_done": 0, "status": "not_started"}
    return data

def generate_progress_components():
    files = [
        os.path.join(LOGS_DIR, f)
        for f in sorted(os.listdir(LOGS_DIR))
        if os.path.isfile(os.path.join(LOGS_DIR, f))
    ]
    # print(files)
    components = []
    for file in files:
        progress = get_progress_from_file(file)
        print(progress)
        progress_bar = dbc.Row(
            [
                dbc.Col(file),
                dbc.Col(
                    dbc.Progress(
                        id={"type": "progress", "index": file},
                        value=progress,
                        animated=True,
                        striped=True,
                        color="primary",
                    )
                ),
            ]
        )
        # print(progress_bar)
        components.append(progress_bar)
    return components



