# Use a base image with mamba pre-installed
FROM mambaorg/micromamba:0.15.3

# Copy the conda environment file
COPY conda/fastapi_backend_env.yaml /tmp/fastapi_backend_env.yaml

# Create the conda environment using mamba
RUN micromamba install -y -n base -f /tmp/fastapi_backend_env.yaml && \
    micromamba clean --all --yes

# # Set the ENTRYPOINT to /opt/conda/bin/python (optional)
# ENTRYPOINT ["/opt/conda/bin/python"]

# Default command to run when the container starts
CMD [ "/opt/conda/bin/python", "run.py" ]
