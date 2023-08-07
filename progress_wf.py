import dash_bootstrap_components as dbc
from dash import Input, Output, dcc, html
import dash
import os
import re

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

LOGS_DIR = "logs_mosaicatcher/selected_logs/"
pattern = re.compile(r"\d+ of \d+ steps \(\d+%\) done")


def get_progress_from_file(file_path):
    with open(file_path, "r") as f:
        log_content = f.read()
    log_lines = [e for e in log_content.strip().split("\n") if pattern.match(e)][-1]
    # for line in log_lines:
    #     if pattern.match(line):
    print(log_lines)
    progress = int(re.search(r"\((\d+)%\)", log_lines).group(1))
    print(progress)
    return progress


def generate_progress_components():
    files = [
        os.path.join(LOGS_DIR, f)
        for f in sorted(os.listdir(LOGS_DIR))
        if os.path.isfile(os.path.join(LOGS_DIR, f))
    ]
    print(files)
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
        print(progress_bar)
        components.append(progress_bar)
    return components


progress_components = generate_progress_components()
print(progress_components)
app.layout = dbc.Container(
    [
        dcc.Interval(id="progress-interval", n_intervals=0, interval=5000),
        html.Div(id='progress-container')  # This will hold our progress bars
    ],
    fluid=False,
)

@app.callback(
    Output("progress-container", "children"),
    [Input("progress-interval", "n_intervals")]
)
def update_progress(n):
    components = []
    for log_file in sorted(os.listdir(LOGS_DIR)):
        progress = get_progress_from_file(os.path.join(LOGS_DIR, log_file))
        color = "primary"
        animated = True
        striped = True
        label = ""
        
        if progress >= 5:
            label = f"{progress} %"
            
        if progress == 100:
            color = "success"
            animated = False
            striped = False
        
        progress_bar = dbc.Row(
            [
                dbc.Col(log_file),
                dbc.Col(
                    dbc.Progress(
                        value=progress,
                        animated=animated,
                        striped=striped,
                        color=color,
                        label=label
                    )
                ),
            ]
        )
        components.append(progress_bar)

    return components


if __name__ == "__main__":
    app.run_server(debug=True, port=8051)
