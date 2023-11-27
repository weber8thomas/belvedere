import subprocess
import sys, os
import requests
import json

# URL of the Panoptes API
base_url = "http://localhost:8058/api"
url = "http://localhost:8058/api/workflows"


# Function to get all workflows
def get_workflows():
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(
            "Failed to fetch data: Status code {}".format(response.status_code)
        )


# Function to find a workflow ID by name
def find_workflow_id_by_name(workflows, name):
    for workflow in workflows.get("workflows", []):
        if workflow["name"] == name:
            return workflow["id"]
    return None


# Function to list all workflow IDs that do not contain "pipeline" in their name
def list_non_pipeline_workflows(workflows):
    non_pipeline_ids = []
    for workflow in workflows.get("workflows", []):
        if "pipeline" not in workflow["name"]:
            non_pipeline_ids.append(workflow["id"])
            print(workflow)
    return non_pipeline_ids


# Function to delete a workflow by ID using the API
def delete_workflow_api(workflow_id):
    delete_url = f"{base_url}/workflow/{workflow_id}"
    response = requests.delete(delete_url)
    print("delete_workflow_api")
    print(delete_url)
    print(response.status_code)
    if response.status_code == 204:
        return True, response.status_code
    elif response.status_code == 403:
        return False, response.status_code
    else:
        print(f"Error: {response.status_code}, {response.json()}")
        return False, None


# Function to delete a workflow by ID from the database
def delete_workflow_db(workflow_id, db_path):
    try:
        command = f'sqlite3 {db_path} "DELETE FROM workflows WHERE id={workflow_id};"'
        subprocess.run(command, shell=True, check=True)
        print(f"Deleted ID {workflow_id} from the database.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error while trying to delete ID {workflow_id} from the database: {e}")
        return False


# Combined delete function
def delete_workflow(workflow_id, db_path, force=False):
    print("Delete workflow")
    print(workflow_id)
    success, error_code = delete_workflow_api(workflow_id)
    if not success and force:
        print(
            f"API deletion failed for ID {workflow_id}. Attempting direct database deletion..."
        )
        return delete_workflow_db(workflow_id, db_path)
    return success


# Main script
if __name__ == "__main__":
    try:
        mode = sys.argv[1]

        force_flag = True
        workflows_data = get_workflows()
        database_path = ".panoptes.db"

        if mode == "retrieve_id":
            workflow_name = str(sys.argv[2])  # Workflow name
            delete_flag = sys.argv[3].lower() == "true"  # Delete flag

            workflow_id = find_workflow_id_by_name(workflows_data, workflow_name)
            if workflow_id is not None:
                print(f"Workflow ID for '{workflow_name}': {workflow_id}")
                if delete_flag:
                    force_flag = True
                    if delete_workflow(workflow_id, database_path, force_flag):
                        print(f"Workflow '{workflow_name}' deleted successfully.")
                    else:
                        print("Failed to delete workflow.")
            else:
                print(f"No workflow found with name '{workflow_name}'")

        elif mode == "list_unnamed_workflows":
            delete_flag = sys.argv[2].lower() == "true"  # Delete flag

            non_pipeline_ids = list_non_pipeline_workflows(workflows_data)
            print("Workflows IDs without 'pipeline' in their name:", non_pipeline_ids)

            if delete_flag:
                for workflow_id in non_pipeline_ids:
                    if delete_workflow(workflow_id, database_path, force_flag):
                        print(f"Workflow with ID {workflow_id} deleted successfully.")
                    else:
                        print(f"Failed to delete workflow with ID {workflow_id}")

    except Exception as e:
        print(e)
