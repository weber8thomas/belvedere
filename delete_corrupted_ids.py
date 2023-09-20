import subprocess
import sys


def delete_from_db(id_list):
    for _id in id_list:
        try:
            command = """
            sqlite3 .panoptes.db "ATTACH DATABASE '/g/korbel2/weber/workspace/snakemake_logs_dev/.panoptes.db' as panoptes; DELETE FROM workflows WHERE id={};"
            """.format(
                _id
            )
            subprocess.run(command, shell=True, check=True)
            print(f"Deleted ID {_id} from the database.")
        except subprocess.CalledProcessError:
            print(f"Error while trying to delete ID {_id} from the database.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script_name.py id1 id2 ...")
        sys.exit(1)

    ids_to_delete = [int(arg) for arg in sys.argv[1:]]
    delete_from_db(ids_to_delete)
