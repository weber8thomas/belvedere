import os, sys
import yaml

configfile = "config.yaml"

def load_config(configfile=configfile):
    # Load the metadata
    with open(configfile, "r") as stream:
        try:
            config = yaml.safe_load(stream)
            return config
        except yaml.YAMLError as exc:
            sys.exit("YAML config not existing")

