import dash
import dash_bootstrap_components as dbc
from dash import dcc, html
from dash.dependencies import Input, Output, State
import subprocess
import yaml
import json

# Load the metadata
with open("config.yaml", "r") as stream:
    try:
        metadata = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)
        metadata = {}

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Define the categories for grouping the parameters
categories = ["General", "Normalization", "Genecore", "ArbiGent", "Other"]

# Group parameters by category (for simplicity, we will categorize based on the initial character)
category_metadata = {
    category: {k: v for k, v in metadata.items() if k[0].lower() == category[0].lower()}
    for category in categories
}

def generate_form_element(meta, id):
    if meta["type"] == "bool":
        input_element = dbc.Checklist(id=id, options=[{"label": "", "value": 1}], inline=True, switch=True, value=[1]) if meta['type'] == 'bool' else dbc.Input(id=id, type=meta['type'])
        
    else:
        input_element = dbc.Input(id=id, type="text", value=meta.get("default", ""), className="m-0 p-0")

    return html.Div([
                dbc.Card([
                    html.Div([
                        html.Label(id, className="font-weight-bold text-white p-2", style={"backgroundColor": "#6c757d", "marginLeft": "0px"}),
                        html.Div([input_element], style={"display": "inline-block", "verticalAlign": "middle", "marginLeft": "20px"})
                    ], style={"display": "flex", "alignItems": "center"}),
                ], className="p-2", style={"border": "1px solid grey", "padding": "10px 0px"}),
                html.Small(meta['desc'], className="text-muted")
            ], className="mb-2")

app.layout = html.Div([
    dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    html.H3(category, className="mb-2 p-2"),
                    * [generate_form_element(meta, id) for id, meta in category_metadata[category].items()]
                ], className="mb-3 p-2 bg-white") for category in categories
            ], width=6, className="mx-auto")  # Adjusted alignment
        ]),
        dbc.Row([
            dbc.Col(
                dbc.Button("Run pipeline", id="run-button", color="primary", className="mt-3", style={'width': '20%'}),
                width=6, className="mx-auto"  # Adjusted button alignment
            )
        ])
    ], fluid=True, className="p-4 bg-light")
], style={"height": "100vh"})



@app.callback(
    Output("run-button", "disabled"),
    [
        Input(id, "value")
        for category in categories
        for id in category_metadata[category]
    ],
)
def validate_inputs(*values):
    # Implement validation logic here
    return False


@app.callback(
    Output("run-button", "children"),
    [Input("run-button", "n_clicks")],
    [
        State(id, "value")
        for category in categories
        for id in category_metadata[category]
    ],
)
def run_pipeline(n, *values):
    if n is None:
        return "Run pipeline"

    # Build the command
    cmd = ["snakemake", "--config"]
    for id, value in zip(
        [id for category in categories for id in category_metadata[category]], values
    ):
        if (
            isinstance(value, list) and len(value) > 0 and value[0] == 1
        ):  # Boolean switch
            cmd.append(f"{id}=True")
        else:
            cmd.append(f"{id}={value}")

    # Run the command
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        return f"Error: {stderr.decode('utf-8')}"

    return "Pipeline ran successfully!"


if __name__ == "__main__":
    app.run_server(debug=True)
