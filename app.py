from dash_iconify import DashIconify
import subprocess
from dash import Dash, html, dcc, Input, Output, State, ALL, MATCH
import os
import pandas as pd
import dash_bootstrap_components as dbc
import dash
import dash_ag_grid as dag
from pprint import pprint
import yaml
import time


import dash_mantine_components as dmc
from dash import html, Output, Input, State

# STRAND-SCAPE
from utils import merge_labels_and_info, get_files_structure
from utils import columnDefs, defaultColDef, SIDEBAR_STYLE, CONTENT_STYLE

# BELVEDERE
from utils import categories, category_metadata, generate_form_element

# PROGRESS
from utils import LOGS_DIR, get_progress_from_file, get_progress_from_api

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
server = app.server

root_folder = os.path.expanduser("/Users/tweber/Gits/belvedere/data")


data = get_files_structure(root_folder)


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
            dbc.Row(
                [
                    dbc.Col(DashIconify(icon="mdi:eiffel-tower", width=20), width=1),
                    dbc.Col(dmc.Title("Belvedere", order=4)),
                ]
            )
        ),
        html.Hr(),
        # html.H5("Year selection:"),
        # dcc.Dropdown(
        #     id="year-dropdown",
        #     options=[{"label": year, "value": year} for year in sorted(data.keys())],
        #     placeholder="Select a year",
        # ),
        # html.Br(),
        # html.H5("Run selection:"),
        # dcc.Dropdown(id="run-dropdown", placeholder="Select a run",
        # options=[{"label": run, "value": run} for run in sorted(data.keys())]
        # ),
        # html.Hr()
        # html.Br(),
        # html.H5("Sample selection:"),
        # dcc.Dropdown(id="sample-dropdown", placeholder="Select a sample"),
        html.Hr(),
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


# @app.callback(
#     [
#         Output("url", "pathname"),
#         Output("warning-modal", "is_open"),
#         Output("modal-header", "children"),
#         Output("modal-body", "children"),
#     ],
#     [Input("run-dropdown", "value"), Input("sample-dropdown", "value"), Input('run-mosaicatcher-button', 'n_clicks')],
#     [State("url", "pathname")],
# )
# def on_button_click(run, sample, redirect_clicks, pathname):
#     print(run, sample)
#     hand_labels_path = f"data/{run}/{sample}/cell_selection/labels_hand.tsv"
#     check_hand_labels_exist = os.path.isfile(hand_labels_path)
#     if redirect_clicks == 0:  # button has not been clicked yet
#         return pathname, False, dash.no_update, dash.no_update

#     else:
#         if check_hand_labels_exist is False:  # Save button was not clicked
#             header = html.H1("Warning!", className="text-warning")
#             body = html.H5(
#                 "The 'Save' button was not clicked for the current run & sample. Please save before proceeding.",
#                 className="text-warning",
#             )
#             return pathname, True, header, body  # show modal
#         else:
#             return '/belvedere', False, dash.no_update, dash.no_update  # go to /belvedere


# Enable Belvedere button when Save button is clicked
@app.callback(
    [
        Output({"type": "run-mosaicatcher-button", "index": MATCH}, "disabled"),
        Output({"type": "stored-save-button", "index": MATCH}, "data"),
        Output({"type": "stored-selectedRows", "index": MATCH}, "data"),
    ],
    [
        Input({"type": "save-button", "index": MATCH}, "n_clicks"),
        # Input("run-dropdown", "value"),
        # Input("sample-dropdown", "value"),
        Input("url", "pathname"),
        Input("interval", "n_intervals"),
    ],
    [
        State({"type": "selection-checkbox-grid", "index": MATCH}, "selectedRows"),
        State({"type": "selection-checkbox-grid", "index": MATCH}, "rowData"),
        State({"type": "stored-save-button", "index": MATCH}, "data"),
        State({"type": "stored-selectedRows", "index": MATCH}, "data"),
    ],
    prevent_initial_call=True,
)
def disable_redirect_button(
    n_clicks,
    # run,
    # sample,
    url,
    n_intervals,
    selected_rows,
    df,
    stored_save_button,
    stored_selected_rows,
):
    if url != "/":
        run, sample = url.split("/")[1:3]
        print(run, sample)
        processed_df_path = (
            f"{root_folder}/{run}/{sample}/cell_selection/labels_belvedere.tsv"
        )
        # if os.path.isfile(processed_df_path):
        #     return False, stored_save_button, stored_selected_rows
        # else:

        print(stored_save_button)
        if n_clicks:
            print(n_clicks, stored_save_button["n_clicks"])
            if n_clicks > stored_save_button["n_clicks"]:
                print("TATA")
                # print(n_clicks)

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

                processed_df.to_csv(processed_df_path, sep="\t", index=False)
                # print(processed_df)
                stored_save_button["run_mosaicatcher_disabled"] = False
                return (
                    stored_save_button["run_mosaicatcher_disabled"],
                    stored_save_button,
                    selected_rows,
                )
            else:
                return (
                    stored_save_button["run_mosaicatcher_disabled"],
                    stored_save_button,
                    stored_selected_rows,
                )
        else:
            return (
                stored_save_button["run_mosaicatcher_disabled"],
                stored_save_button,
                stored_selected_rows,
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


# @app.callback(Output("url", "pathname"), [Input("run-mosaicatcher-button", "n_clicks")])
# def on_button_click(n):
#     if n is not None:  # button has been clicked
#         return "/belvedere"


main_content = html.Div(
    [
        html.Div(
            id="output-container",
            style=CONTENT_STYLE,
        ),
    ]
)


# @app.callback(
#     Output("run-dropdown", "options"),
#     Output("run-dropdown", "value"),
#     Input("year-dropdown", "value"),
# )
# def update_run_dropdown(selected_year):
#     if selected_year:
#         runs = data[selected_year]
#         return [{"label": run, "value": run} for run in runs], list(runs)[0]
#     else:
#         return [], None


# @app.callback(
#     Output("url", "pathname"),
#     Input("year-dropdown", "value"),
#     Input("run-dropdown", "value"),
#     Input("sample-dropdown", "value"),
# )
# def update_url(year, run, sample):
#     if year and run and sample:
#         return f"/{year}/{run}/{sample}"
#     return "/"


# @app.callback(
#     Output("run-dropdown", "options"),
#     Input("year-dropdown", "value"),
#     prevent_initial_call=True,
# )
# def set_run_options(selected_year):
#     if selected_year is None:
#         raise dash.exceptions.PreventUpdate
#     run_names = data[selected_year].keys()
#     return [{"label": run_name, "value": run_name} for run_name in run_names]


@app.callback(
    Output("run-dropdown", "value"),
    Input("run-dropdown", "data"),
    prevent_initial_call=True,
)
def set_run_value(options):
    if options is None:
        raise dash.exceptions.PreventUpdate
    return options[0]["value"] if options else None


@app.callback(
    Output("sample-dropdown", "data"),
    # Input("year-dropdown", "value"),
    Input("run-dropdown", "data"),
    prevent_initial_call=True,
)
def set_sample_options(selected_run):
    if selected_run is None:
        raise dash.exceptions.PreventUpdate
    sample_names = data[selected_run]
    return [
        {"label": sample_name, "value": sample_name} for sample_name in sample_names
    ]


# @app.callback(
#     Output("sample-dropdown", "value"),
#     Input("sample-dropdown", "options"),
#     prevent_initial_call=True,
# )
# def set_sample_value(options):
#     return options[0]["value"] if options else None


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
        return not is_open, stored_selected_rows
    return is_open, stored_selected_rows


# Fill the offcanvas with the datatable
@app.callback(
    Output("output-container", "children"),
    Output("output-container", "style"),
    [
        # Input("run-dropdown", "value"),
        # Input("sample-dropdown", "value"),
        Input("url", "pathname"),
    ],
    # prevent_initial_call=True,
)
def fill_sample_wise_container(url):
    if url == "/":
        return html.Div(id="landing-page"), CONTENT_STYLE

    else:
        selected_run, selected_sample = url.split("/")[1:3]
        print(selected_run, selected_sample)
        if selected_run and selected_sample:
            df = merge_labels_and_info(
                f"data/{selected_run}/{selected_sample}/cell_selection/labels.tsv",
                f"data/{selected_run}/{selected_sample}/counts/{selected_sample}.info_raw",
            )

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

            offcanvas = dbc.Offcanvas(
                [
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
                                    style={"width": "20%", "align": "center"},
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

            stored_components_buttons = html.Div(
                [
                    dcc.Store(
                        {
                            "type": "stored-report-button-ashleys",
                            "index": f"{selected_run}--{selected_sample}",
                        },
                        storage_type="session",
                        data=0,
                    ),
                    dcc.Store(
                        {
                            "type": "stored-save-button",
                            "index": f"{selected_run}--{selected_sample}",
                        },
                        storage_type="session",
                        data={"n_clicks": 0, "run_mosaicatcher_disabled": True},
                    ),
                    dcc.Store(
                        {
                            "type": "stored-selectedRows",
                            "index": f"{selected_run}--{selected_sample}",
                        },
                        storage_type="session",
                        data=df.loc[
                            (df["prediction"] == 1) & (df["pass1"] == 1)
                        ].to_dict("records"),
                    ),
                    dcc.Store(
                        {
                            "type": "stored-homepage-button",
                            "index": f"{selected_run}--{selected_sample}",
                        },
                        storage_type="session",
                        data=0,
                    ),
                    dcc.Store(
                        {
                            "type": "stored-report-button-mosaicatcher",
                            "index": f"{selected_run}--{selected_sample}",
                        },
                        storage_type="session",
                        data=0,
                    ),
                    dcc.Store(
                        {
                            "type": "stored-run-mosaicatcher-button",
                            "index": f"{selected_run}--{selected_sample}",
                        },
                        storage_type="session",
                        data={"n_clicks": 0, "disabled": True},
                    ),
                    dcc.Store(
                        id={
                            "type": "stored-progress",
                            "index": f"{selected_run}--{selected_sample}",
                        },
                        storage_type="session",
                        data={"progress": 0, "children": None},
                    ),
                ]
            )

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
                            # gradient={"from": "grape", "to": "pink", "deg": 35},
                            # color="blue",
                            n_clicks=0,
                            size="lg",
                            leftIcon=DashIconify(icon="mdi:home"),
                        ),
                        dmc.Button(
                            "Display Ashleys-QC report",
                            id={
                                "type": "report-button-ashleys",
                                "index": f"{selected_run}--{selected_sample}",
                            },
                            radius="xl",
                            # variant="gradient",
                            # gradient={"from": "grape", "to": "pink", "deg": 35},
                            color="pink",
                            size="lg",
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
                            # variant="gradient",
                            color="orange",
                            disabled=True,
                            size="lg",
                            leftIcon=DashIconify(icon="mdi:hand-tap"),
                        ),
                        dmc.Button(
                            "Run MosaiCatcher",
                            id={
                                "type": "run-mosaicatcher-button",
                                "index": f"{selected_run}--{selected_sample}",
                            },
                            radius="xl",
                            # variant="gradient",
                            # gradient={"from": "teal", "to": "lime", "deg": 105},
                            color="red",
                            n_clicks=0,
                            disabled=True,
                            size="lg",
                            leftIcon=DashIconify(icon="ooui:logo-wikimedia-discovery"),
                        ),
                        dmc.Button(
                            "Display MosaiCatcher report",
                            id={
                                "type": "report-button-mosaicatcher",
                                "index": f"{selected_run}--{selected_sample}",
                            },
                            radius="xl",
                            n_clicks=0,
                            # variant="gradient",
                            # gradient={"from": "orange", "to": "red"},
                            color="grape",
                            disabled=True,
                            size="lg",
                            leftIcon=DashIconify(icon="mdi:eye"),
                        ),
                    ],
                )
            )

            report_wise_div = html.Div(
                [
                    html.Div(
                        dmc.Center(
                            [
                                dmc.Title(
                                    f"Run : {selected_run} - Sample: {selected_sample}",
                                    order=2,
                                    style={
                                        "paddingBottom": "20px",
                                        "paddingTop": "20px",
                                    },
                                ),
                            ],
                        ),
                    ),
                    html.Hr(),
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
            )

            return report_wise_div, CONTENT_STYLE


@app.callback(
    [
        Output({"type": "report-button-ashleys", "index": MATCH}, "disabled"),
        Output({"type": "open-button", "index": MATCH}, "disabled"),
        # Output({"type": "run-mosaicatcher-button", "index": MATCH}, "disabled"),
    ],
    [
        Input({"type": "stored-progress", "index": MATCH}, "data"),
        # Input("run-dropdown", "value"),
        # Input("sample-dropdown", "value"),
        Input("url", "pathname"),
        Input("interval", "n_intervals"),
    ],
)
def disable_report_button(progress_store, url, n):
    if progress_store["progress"] == 100:
        return False, False
    else:
        return True, True


@app.callback(
    [
        Output("landing-page", "children"),
        # Output({"type": "stored-progress", "index": MATCH}, "data"),
    ],
    [
        # Input("url", "pathname"),
        Input("interval-progress", "n_intervals"),
        # Input("run-dropdown", "value"),
        # Input("sample-dropdown", "value"),
    ],
    [
        # State({"type": "stored-progress", "index": MATCH}, "data"),
    ],
    # prevent_initial_call=True,
)
def update_progress(n):
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
                ]
            ),
        ]
    )

    dropdown_components = [
        dbc.Col(
            [
                dmc.MultiSelect(
                    id="run-dropdown",
                    placeholder="Select a run",
                    data=[{"label": run, "value": run} for run in sorted(data.keys())],
                    persistence=True,
                    persistence_type="session",
                    # radius="xl",
                    searchable=True,
                    clearable=True,
                    # size="md",
                )
            ],
            width=3,
        ),
        dbc.Col(
            [
                dmc.MultiSelect(
                    id="sample-dropdown",
                    data=[
                        {"label": sample, "value": sample}
                        for run in sorted(data.keys())
                        for sample in sorted(data[run])
                    ],
                    placeholder="Select a sample",
                    persistence=True,
                    persistence_type="session",
                    # radius="xl",
                    searchable=True,
                    clearable=True,
                    # size="md",
                ),
            ],
            width=3,
        ),
        dbc.Col(width=3),
        dbc.Col(width=3),
    ]

    headers = ["Run", "Sample", "Ashleys-QC progress", "MosaiCatcher progress"]
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
            width=3,
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
                html.Div(id="progress-container-landing-page"),
            ]
        )
    ]

    return components


@app.callback(
    Output("progress-container-landing-page", "children"),
    [
        Input("interval-progress", "n_intervals"),
        Input("run-dropdown", "value"),
        Input("sample-dropdown", "value"),
    ],
)
def update_progress(n, dropdown_run, dropdown_sample):
    print(dropdown_run, dropdown_sample)
    import time
    import requests
    from requests.exceptions import Timeout

    url_api = "http://127.0.0.1:8058/api/workflows"

    max_retries = 3  # Maximum number of times to retry the request
    wait_time = 5  # Time to wait between retries (in seconds)

    for _ in range(max_retries):
        print(_)
        try:
            response_json = requests.get(
                url_api, headers={"Accept": "application/json"}
            ).json()
            print(response_json)
            # Break out of the loop if the request is successful
            break
        except Timeout:
            print(
                f"Timeout error: Attempt {_ + 1} of {max_retries}. Retrying in {wait_time} seconds."
            )
            if _ == max_retries - 1:
                print(
                    f"Failed to fetch progress from API after {max_retries} attempts."
                )
                return [
                    html.Div("Error fetching progress. Please try again later."),
                    # progress_store,
                ]
            time.sleep(wait_time)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return [
                html.Div("An unexpected error occurred. Please try again later."),
                # progress_store,
            ]

    # Extract data

    data_lite = [f"{k}--{e}" for k, v in data.items() for e in sorted(v)]
    # response_json = requests.get(url, headers={"Accept": "application/json"}).json()
    data_panoptes = [wf for wf in response_json["workflows"] if wf["name"] in data_lite]
    print(data_panoptes)
    for run_sample in data_lite:
        if run_sample not in [wf["name"] for wf in data_panoptes]:
            data_panoptes.append(
                {
                    "name": run_sample,
                    "jobs_total": 0,
                    "jobs_done": 0,
                    "status": "not_started",
                }
            )

    if dropdown_run:
        data_panoptes = [e for e in data_panoptes if e["name"].split("--")[0] in dropdown_run]
    if dropdown_sample:
        data_panoptes = [e for e in data_panoptes if e["name"].split("--")[1] in dropdown_sample]

    print(data_lite)
    # print(headers_components)
    # print(components)
    components = []

    # Generate progress bars
    for entry in data_panoptes:
        print(entry)
        status = entry["status"]
        if status != "not_started":
            progress = round((entry["jobs_done"] / entry["jobs_total"]) * 100, 2)
        else:
            progress = 0

        color = "primary"
        animated = True
        striped = True
        label = ""

        # if progress >= 5:
        label = f"{status} - {progress} %"

        if progress == 100 and status == "Done":
            color = "success"
            animated = False
            striped = False
            disabled = False
        elif progress < 100 and status == "Error":
            color = "danger"
            animated = False
            striped = False
        elif progress < 100 and status == "Running":
            color = "primary"
            animated = True
            striped = True
        elif progress == 0 and status == "not_started":
            color = "grey"
            animated = False
            striped = False
            print("TOTO")
            label = "Not Started"

        run, sample = entry["name"].split("--")

        progress_bar = dbc.Row(
            [
                dbc.Col(
                    [
                        dmc.Text(
                            run,
                            size="lg",
                            weight=400,
                            # style={"paddingBottom": "20px", "paddingTop": "20px"},
                        ),
                    ],
                    width=3,
                ),
                dbc.Col(
                    [
                        dcc.Link(
                            [
                                dmc.Text(
                                    sample,
                                    size="lg",
                                    weight=400,
                                    # style={"paddingBottom": "20px", "paddingTop": "20px"},
                                )
                            ],
                            href=f"/{run}/{sample}",
                            style={"color": "black", "text-decoration": "none"},
                        ),
                    ],
                    width=3,
                ),
                dbc.Col(
                    dbc.Progress(
                        value=progress,
                        animated=animated,
                        striped=striped,
                        color=color,
                        label=label,
                        style={"height": "30px"},
                    ),
                    width=3,
                ),
                dbc.Col(
                    dbc.Progress(
                        value=progress,
                        animated=animated,
                        striped=striped,
                        color=color,
                        label=label,
                        style={"height": "30px"},
                    ),
                    width=3,
                ),
            ],
            style={"height": "40px"},
        )
        components.append(progress_bar)

    # Store components and progress (if needed)
    # progress_store["children"] = components
    print(components)

    # Initialize components
    print(dropdown_run, dropdown_sample)
    # if run and sample:
    return components
    # else:
    #     return []


@app.callback(
    [
        Output({"type": "run-progress-container", "index": MATCH}, "children"),
        Output({"type": "stored-progress", "index": MATCH}, "data"),
    ],
    [
        Input("interval-progress", "n_intervals"),
        # Input("run-dropdown", "value"),
        # Input("sample-dropdown", "value"),
        Input("url", "pathname"),
    ],
    [
        State({"type": "stored-progress", "index": MATCH}, "data"),
    ],
    prevent_initial_call=True,
)
def update_progress(n, url, progress_store):
    if url == "/":
        return html.Div(), progress_store
    else:
        run, sample = url.split("/")[1:3]
        disabled = True
        print(run, sample)
        print(progress_store)
        return html.Div(), progress_store
    # if (progress_store["progress"] < 100) or (progress_store["children"] is None):
    #     print("TOTO")
    #     index = "TMP"
    #     components = []

    #     max_retries = 3  # Maximum number of times to retry the request
    #     wait_time = 5  # Time to wait between retries (in seconds)

    #     for _ in range(max_retries):
    #         try:
    #             panoptes_json = get_progress_from_api(run, sample)
    #             # Break out of the loop if the request is successful
    #             break
    #         except Exception as e:
    #             # If it's the last iteration, raise the exception
    #             if _ == max_retries - 1:
    #                 print(
    #                     f"Failed to fetch progress from API after {max_retries} attempts."
    #                 )
    #                 return [
    #                     html.Div("Error fetching progress. Please try again later."),
    #                     progress_store,
    #                 ]
    #             # If it's not the last iteration, wait for some time and then retry
    #             time.sleep(wait_time)
    #             continue

    #     # print(panoptes_json)
    #     status = panoptes_json["status"]

    #     if status != "not_started":
    #         progress = round(
    #             (panoptes_json["jobs_done"] / panoptes_json["jobs_total"]) * 100, 2
    #         )
    #     else:
    #         progress = 0

    #     color = "primary"
    #     animated = True
    #     striped = True
    #     label = ""

    #     # if progress >= 5:
    #     label = f"{status} - {progress} %"

    #     if progress == 100 and status == "Done":
    #         color = "success"
    #         animated = False
    #         striped = False
    #         disabled = False
    #     elif progress < 100 and status == "Error":
    #         color = "danger"
    #         animated = False
    #         striped = False
    #     elif progress < 100 and status == "Running":
    #         color = "primary"
    #         animated = True
    #         striped = True
    #     elif progress == 0 and status == "not_started":
    #         color = "grey"
    #         animated = False
    #         striped = False
    #         print("TOTO")
    #         label = "Not Started"

    #     print(label)
    #     if progress > 0:
    #         progress_bar = dbc.Row(
    #             [
    #                 # dbc.Col(
    #                 #     [
    #                 #         dmc.ActionIcon(
    #                 #             DashIconify(icon="mdi:eye"),
    #                 #             variant="outline",
    #                 #             color="blue",
    #                 #             disabled=disabled,
    #                 #             id={"type": "report-button", "index": index},
    #                 #         ),
    #                 #     ],
    #                 #     width="auto",
    #                 # ),
    #                 # dbc.Col(log_file),
    #                 dbc.Col(
    #                     dbc.Progress(
    #                         value=progress,
    #                         animated=animated,
    #                         striped=striped,
    #                         color=color,
    #                         label=label,
    #                         style={"height": "30px"},
    #                     )
    #                 ),
    #             ],
    #             style={"height": "40px"},
    #         )
    #         components.append(progress_bar)

    #     else:
    #         components.append(html.Div("Progress bar not available yet"))
    #     progress_store["children"] = components
    #     progress_store["progress"] = progress
    #     # print(components)
    #     # print(progress_store)
    #     return components, progress_store
    # else:
    #     # progress_store["children"] = [html.Div("Progress bar not available yet")]
    #     return progress_store["children"], progress_store


@app.callback(
    Output({"type": "metadata-container", "index": MATCH}, "children"),
    [
        # Input("sample-dropdown", "value"),
        # Input("run-dropdown", "value"),
        Input("url", "pathname"),
        Input({"type": "homepage-button", "index": MATCH}, "n_clicks"),
    ],
    prevent_initial_call=True,
)
def fill_metadata_container(url, n_clicks):
    if url == "/":
        raise dash.exceptions.PreventUpdate
    else:
        run, sample = url.split("/")[1:3]
        index = "PE20"
        genecore_filepath = f"/g/korbel/STOCKS/Sequencing/2023/{run}"
        pipeline_processed_data_filepath = (
            f"/scratch/tweber/DATA/MC_DATA/STOCKS/Sequencing/{run}/{sample}"
        )
        backup_processed_data_filepath = f"/g/korbel/WORKFLOW_RESULTS/{run}/{sample}"

        metadata_dict = {
            "Sample name": sample,
            "Run name": run,
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
            ]
        )

        return card


@app.callback(
    [
        Output({"type": "run-sample-container", "index": MATCH}, "children"),
        Output({"type": "stored-homepage-button", "index": MATCH}, "data"),
        Output({"type": "stored-report-button-ashleys", "index": MATCH}, "data"),
        Output({"type": "stored-run-mosaicatcher-button", "index": MATCH}, "data"),
        Output({"type": "stored-report-button-mosaicatcher", "index": MATCH}, "data"),
        # Output({"type": "stored-progress", "index": MATCH}, "data"),
    ],
    [
        Input({"type": "homepage-button", "index": MATCH}, "n_clicks"),
        Input({"type": "report-button-ashleys", "index": MATCH}, "n_clicks"),
        Input({"type": "run-mosaicatcher-button", "index": MATCH}, "n_clicks"),
        Input({"type": "report-button-mosaicatcher", "index": MATCH}, "n_clicks"),
        Input("url", "pathname"),
        # Input("run-dropdown", "value"),
        # Input("sample-dropdown", "value"),
    ],
    [
        State({"type": "stored-homepage-button", "index": MATCH}, "data"),
        State({"type": "stored-report-button-ashleys", "index": MATCH}, "data"),
        State({"type": "stored-run-mosaicatcher-button", "index": MATCH}, "data"),
        State({"type": "stored-report-button-mosaicatcher", "index": MATCH}, "data"),
        # State({"type": "stored-progress", "index": MATCH}, "data"),
    ],
    # prevent_initial_call=True,
)
def populate_container_sample(
    n_clicks_homepage_button,
    n_clicks_report_ashleys_button,
    n_clicks_beldevere_button,
    n_clicks_report_mosaicatcher_button,
    url,
    # selected_run,
    # selected_sample,
    report_homepage_button_stored,
    report_ashleys_button_stored,
    beldevere_button_stored,
    report_mosaicatcher_button_stored,
    # progress_store,
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
        genecore_filepath = f"/g/korbel/STOCKS/Sequencing/2023/{selected_run}"
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

        homepage_layout = html.Div(
            children=[
                dmc.Title(
                    f"{selected_sample} metadata",
                    order=2,
                    style={"paddingTop": "20px", "paddingBottom": "20px"},
                ),
                card,
                html.Hr(),
                dmc.Title(
                    "Ashleys-QC run",
                    order=2,
                    style={"paddingTop": "20px", "paddingBottom": "20px"},
                ),
                html.Div(
                    id={
                        "type": "run-progress-container",
                        "index": f"{selected_run}--{selected_sample}",
                    },
                ),
                html.Hr(),
                dmc.Title(
                    "MosaiCatcher run",
                    order=2,
                    style={"paddingTop": "20px", "paddingBottom": "20px"},
                ),
                # html.Div(
                #     id={
                #         "type": "run-progress-container",
                #         "index": f"mosaicatcher-{selected_run}--{selected_sample}",
                #     },
                # ),
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
            return (
                [
                    html.Iframe(
                        src=dash.get_asset_url(
                            f"watchdog_ashleys_data/{selected_run}/{selected_sample}/report.html"
                        ),
                        style={"width": "100%", "height": "900px"},
                    )
                ],
                n_clicks_homepage_button,
                n_clicks_report_ashleys_button,
                n_clicks_beldevere_button,
                n_clicks_report_mosaicatcher_button,
                # progress_store,
            )
        elif (
            n_clicks_beldevere_button
            and n_clicks_beldevere_button > beldevere_button_stored
        ):
            form_element = generate_form_element(selected_run, selected_sample)
            x = 52
            color_x = "green" if x > 50 else "red"
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
                                            form_element,
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
                                                dmc.Button(
                                                    "Run MosaiCatcher",
                                                    id="run-button",
                                                    color="red",
                                                    variant="filled",
                                                    # gradient={
                                                    #     "from": "teal",
                                                    #     "to": "lime",
                                                    #     "deg": 105,
                                                    # },
                                                    className="mt-3",
                                                    style={"width": "auto"},
                                                    size="xl",
                                                    radius="xl",
                                                    leftIcon=DashIconify(
                                                        icon="zondicons:play-outline"
                                                    ),
                                                )
                                            ]
                                        ),
                                        width=6,
                                        className="mx-auto",  # Adjusted button alignment
                                    ),
                                ]
                            ),
                        ],
                        fluid=False,
                        # className="p-4 bg-light",
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
                # progress_store,
            )
        else:
            print("TOTO")
            # return (
            #     html.Div(dmc.Title("Please select a run and sample", order=2)),
            #     n_clicks_homepage_button,
            #     n_clicks_report_ashleys_button,
            #     # n_clicks_report_mosaicatcher_button,
            #     n_clicks_beldevere_button,
            #     # progress_store,
            # )
            return (
                homepage_layout,
                n_clicks_homepage_button,
                n_clicks_report_ashleys_button,
                n_clicks_beldevere_button,
                n_clicks_report_mosaicatcher_button,
                # progress_store,
            )

        # elif (
        #     n_clicks_report_mosaicatcher_button
        #     and n_clicks_report_mosaicatcher_button > report_mosaicatcher_button_stored
        # ):
        #     return (
        #         [
        #             html.Iframe(
        #                 src=dash.get_asset_url(
        #                     f"watchdog_ashleys_data/{selected_run}/{selected_sample}/report.html"
        #                 ),
        #                 style={"width": "100%", "height": "900px"},
        #             )
        #         ],
        #         n_clicks_report_ashleys_button,
        #         n_clicks_report_mosaicatcher_button,
        #         n_clicks_beldevere_button,
        #     )


# @app.callback(
#     Output("run-button", "disabled"),
#     [
#         Input(id, "value")
#         for category in categories
#         for id in category_metadata[category]
#     ],
# )
# def validate_inputs(*values):
#     # Implement validation logic here
#     return False


# @dash.callback(
#     Output("run-button", "children"),
#     [Input("run-button", "n_clicks")],
#     [
#         State(id, "value")
#         for category in categories
#         for id in category_metadata[category]
#     ],
# )
# def run_pipeline(n, *values):
#     if n is None:
#         return "Run pipeline"

#     # Build the command
#     cmd = ["snakemake", "--config"]
#     for id, value in zip(
#         [id for category in categories for id in category_metadata[category]], values
#     ):
#         if (
#             isinstance(value, list) and len(value) > 0 and value[0] == 1
#         ):  # Boolean switch
#             cmd.append(f"{id}=True")
#         else:
#             cmd.append(f"{id}={value}")

#     # Run the command
#     process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     stdout, stderr = process.communicate()

#     if process.returncode != 0:
#         return f"Error: {stderr.decode('utf-8')}"

#     return "Pipeline ran successfully!"


# @app.callback(
#     Output('warning-modal', 'is_open'),
#     [Input('modal-close', 'n_clicks')]
# )
# def close_modal(n):
#     return False


# # Update page
# @app.callback(Output("page-content", "children"), [Input("url", "pathname")])
# def display_page(pathname):
#     if pathname == "/belvedere":
#         return belvedere_layout
#     else:
#         return main_content


# content = html.Div(id="page-content")


app.layout = html.Div(
    [
        dcc.Interval(id="interval", interval=1000, n_intervals=0),
        dcc.Interval(id="interval-progress", interval=5000, n_intervals=0),
        dcc.Location(id="url", refresh=False),
        # navbar,
        sidebar,
        main_content,
        # dash.page_container,
    ]
)


print(data)

if __name__ == "__main__":
    app.run_server(debug=True)
