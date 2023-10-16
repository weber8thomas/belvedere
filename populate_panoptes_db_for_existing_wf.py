import collections
import glob
import os
import re
import sqlite3
from datetime import datetime

path_to_watch = "/g/korbel/WORKFLOW_RESULTS"
# path_to_watch = "/g/korbel/STOCKS/Data/Assay/sequencing/2023"


def extract_samples_names(l, directory_path):
    # print(directory_path)
    # exit()
    samples = list()
    prefixes = list()
    pattern = re.compile(r"_lane1(.*?)(iTRU|PE20)(.*?)([A-H]?)(\d{2})(?:_1_|_2_)")
    for j, file_path in enumerate(sorted(l)):
        if (j + 1) % 192 == 0:
            match = pattern.search(file_path)
            if match:
                sample_name = match.group(1)
                prefixes.append(match.group(2))
                plate = directory_path.split("/")[-1]
                # print(sample_name, plate)
                samples.append(sample_name)

    return prefixes, samples


# Mocked function, replace with your logic
def generate_internal_structure():
    unwanted = ["._.DS_Store", ".DS_Store", "config"]
    total_list_runs = sorted([e for e in os.listdir(path_to_watch) if e not in unwanted])

    dict_structure = collections.defaultdict(list)

    for plate in total_list_runs:
        if plate.startswith("2023"):
            directory_path = f"{path_to_watch}/{plate}"

            for sample in os.listdir(directory_path):
                if sample not in ["config"]:
                    dict_structure[plate].append(sample)

            # prefixes, samples = extract_samples_names(glob.glob(f"{path_to_watch}/{plate}/*.txt.gz"), directory_path)
            # for sample in samples:
            #     if "PDAC6059" not in sample:
            #         print(plate, sample)

    return dict_structure


def create_and_populate_table(connection, structure):
    # Drop existing table
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS workflows")

    # Create new table
    cursor.execute(
        """
        CREATE TABLE workflows (
            id INTEGER NOT NULL,
            name VARCHAR(50),
            status VARCHAR(30),
            done INTEGER,
            total INTEGER,
            started_at DATETIME,
            completed_at DATETIME,
            PRIMARY KEY (id),
            UNIQUE (name)
        )
    """
    )

    # Populate the table with the new structure
    timestamp = datetime.now().isoformat(" ")

    for run, samples in structure.items():
        for sample in samples:
            name = f"ashleys-qc-pipeline--{run}--{sample}"
            cursor.execute(
                """
                INSERT INTO workflows (name, status, done, total, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (name, "Done", 1, 1, timestamp, timestamp),
            )
            print(
                """
                INSERT INTO workflows (name, status, done, total, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (name, "Done", 1, 1, timestamp, timestamp),
            )

    # Commit the changes
    connection.commit()


def main():
    # Create internal structure
    structure = generate_internal_structure()

    # # Connect to the SQLite database (replace with your db name)
    connection = sqlite3.connect(".panoptes.db.bak")

    # Drop existing table, create a new one, and populate
    create_and_populate_table(connection, structure)

    # # Close the connection
    connection.close()


if __name__ == "__main__":
    main()
