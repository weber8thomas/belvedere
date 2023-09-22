
# Strand-Scape v0.2.0 Documentation

Welcome to Strand-Scape v0.2.0, an intuitive web platform designed to enhance the user experience for MosaiCatcher via a graphical interface.

## Introduction

Strand-Scape simplifies the process of utilizing MosaiCatcher by providing a streamlined interface. 


## Running Strand-Scape (admin side)

#TODO 

### Setting Up the Environment
#### Creating the Conda Environment:

First, you need to set up your Python environment. This ensures you have all the necessary dependencies.

```bash
conda create -f conda_env.yaml
conda activate strandscape_env
```

This command creates a new Conda environment based on the specifications listed in the conda_env.yaml file. The environment will have packages such as dash, rabbitmq, fastapi, pika, and more.

#### Configuring the Application:
Update the paths and other necessary configurations in the config.yaml file to match your system's requirements. This file likely contains important settings like directories, URLs, and ports that the application will use.

### Running the Services
For the subsequent steps, consider using screen to run each command in a separate session. This allows the services to run simultaneously.

#### Starting Panoptes:
Monitor your system with the Panoptes command.

```bash
panoptes -v --port 8058
```

#### Launching RabbitMQ:
RabbitMQ is a message broker, allowing different parts of your application to communicate asynchronously.

```bash
rabbitmq-server
```

#### Starting the Publisher:
This script likely sends messages to a queue, to be consumed by other services.

```bash
python publisher.py
```

#### Running the FastAPI Backend:
Start the backend service, which provides an API and potentially processes data.

```bash
python run.py
```

Note: This command triggers the fastapi_backend.py script.

#### Launching the Dash App:
Dash is a Python framework for building analytical web applications. No JavaScript required.

```bash
python app.py
```

### Future Plans
In the future, we plan to simplify this setup using docker-compose. This will allow all services to be started with a single command, ensuring easier deployment and scalability. Keep an eye out for updates.

## Using Strand-Scape (user side)

#TODO
## Structure of Strand-Scape

![Alt text](docs/image.png)

Strand-Scape's architecture consists of two primary sections: Frontend and Backend.

### Frontend

The frontend has two main sub-sections:

1. **Landing Page**: 
    - Displays the workflow progression of Strand-Seq runs and associated samples.
    - Provides insights into generated runs, available samples, and the execution status of the Ashleys-QC pipeline and MosaiCatcher.

2. **Sample Page**: 
    - Accessible by clicking on a specific sample name.
    - Comprises five distinct sections, navigable via individual buttons:
        - **Homepage**: Shows sample metadata and the progression of workflows.
        - **Ashleys-QC Report**: Renders an HTML report from the Ashleys-QC pipeline, presenting various figures and auto-generated results.
        - **Cell Selection**: Features a side "offcanvas" menu to view Ashleys-QC predictions and manage the inclusion or exclusion of libraries for the MosaiCatcher SV calling process. Ensure to **Save** your selections.
        - **Run MosaiCatcher (initially locked)**: Becomes available after saving cell selections. Enables users to configure MosaiCatcher with minimal customization. It displays the count of cells included in the analysis and requires an email input to keep a record of the user conducting each sample analysis.
        - **MosaiCatcher Report (initially locked)**: Becomes accessible post the completion of the MosaiCatcher workflow. Users can view SV-related figures and statistics in a secondary HTML report.
    - The frontend is crafted using Plotly Dash, complemented by the Dash Mantine & Bootstrap frameworks.

### Backend

The backend infrastructure includes:

- **FastAPI Web Server**: An asynchronous server integrated with a pika consumer that connects to the RabbitMQ broker. If the panoptes/pika publisher is offline, the server reverts to loading the most recent status from a backup JSON file. 
  
- **RabbitMQ Broker**: Handles message queues for the system.

- **Pika Publisher**: Periodically queries panoptes (every 30 seconds) to balance system load and publishes updates to the RabbitMQ broker.

- **Panoptes**: Real-time monitoring of snakemake workflows.

## Roadmap and Future Enhancements

- Introducing functional refresh buttons (currently implemented but hidden).
- Define and integrate mapping from snakemake parameters to dash components (text input, number, switch, dropdown) 


---

**⚠️ Warning**

**Please note** that as of now, Strand-Scape is not set up as a standalone user platform. This means:

- All group members have shared access to data that's been generated and processed.
- Once a sample is processed by a user, it cannot be reprocessed by another user. Enhancements in future versions will address this limitation.

---


# Structure summary

- Panoptes: biocontainer
  - Snakemake API monitoring: https://github.com/panoptes-organization/panoptes
  - Container: https://quay.io/repository/biocontainers/panoptes-ui?tab=tags&tag=latest
- Publisher: 
  - Python script based on pika (publish to rabbitmq)
  - Container: docker_recipes/Dockerfile_publisher.dockerfile
- Watcher (python): 
  - Python script that monitors every hour a folder and trigger snakemake through a subprocess if a new folder is detected
  - **Note: This one is optional and could still run independtly in a screen on seneca if needed**
  - Container: docker_recipes/Dockerfile_watcher.dockerfile
- RabbitMQ: 
  - RabbitMQ broker: https://github.com/rabbitmq/rabbitmq-server
  - Container: https://registry.hub.docker.com/_/rabbitmq/
  - K8S docs: https://rabbitmq.com/kubernetes/operator/operator-overview.html
- fastapi_backend:
  - Python fastapi backend that consume rabbitmq messages, serve HTML files and trigger snakemake
  - **Note: Running on K8S/Docker, would it be possible to still trigger a pipeline through my username that fire jobs on slurm?**
  - Container: docker_recipes/Dockerfile_fastapi_backend.dockerfile
- dash_frontend (python): 
  - Python dash frontend that generates the web UI
  - Container: docker_recipes/Dockerfile_dash_frontend.dockerfile