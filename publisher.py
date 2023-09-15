import collections
import datetime
import os
import sys
import pika
import time
import httpx
import json
import yaml
from config import load_config

config = load_config()



def fetch_data_from_api():
    # PANOPTES_API = "http://127.0.0.1:8058"
    PANOPTES_API = config["panoptes"]
    url_api = f"{PANOPTES_API}/api/workflows"
    max_retries = 5
    wait_time = 10

    # with httpx.Client() as client:  # Changed this line
    #     for attempt in range(max_retries):
    try:
        response = httpx.Client().get(url_api, headers={"Accept": "application/json"})
        response.raise_for_status()  # Raise exception for HTTP errors
        response_json = response.json()
        return response_json
    except httpx.ReadTimeout:  # Catching ReadTimeout
        # if attempt == max_retries - 1:
        print(f"Failed to fetch progress from API after {max_retries} attempts.")

        return {}
        # return data
        # print(
        #     f"Timeout error: Attempt {attempt + 1} of {max_retries}. Retrying in {wait_time} seconds."
        # )
        # time.sleep(wait_time)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # print("Loading from JSON file...")
        # data = load_from_json()
        # print(data)
        return {}
        # return data


def get_files_structure(root_folder):
    data_dict = collections.defaultdict(list)
    for run_name_folder in os.listdir(root_folder):
        run_name = run_name_folder
        for sample_folder in os.listdir(os.path.join(root_folder, run_name_folder)):
            sample_name = sample_folder
            data_dict[run_name].append(sample_name)

    return data_dict


def publish_to_rabbitmq(data=dict, exchange=str, queue=str, routing_key=str):
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()

    # Declare a topic exchange
    channel.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)

    # Declare a queue named 'my_queue' with a message TTL of 300000 milliseconds (5 minutes)
    args = {"x-message-ttl": 30000}
    channel.queue_declare(queue=queue, durable=True, arguments=args)

    # Bind the queue to the exchange with the routing key 'latest_status'
    channel.queue_bind(exchange=exchange, queue=queue, routing_key=routing_key)

    # Fetch the current timestamp
    current_timestamp = int(
        datetime.datetime.now().timestamp() * 1000
    )  # Current time in milliseconds

    # Publish the message to the exchange with the 'latest_status' routing key
    channel.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=json.dumps(data),
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
            timestamp=current_timestamp,  # set timestamp
        ),
    )

    connection.close()


def save_to_json(data=dict, filename=str):
    with open(filename, "w") as file:
        json.dump(data, file)


if __name__ == "__main__":


    while True:

        
        # Wf progress status - Panoptes
        data = fetch_data_from_api()
        if data != {}:
            save_to_json(data=data, filename=config["panoptes"]["json_status_backup"])
        publish_to_rabbitmq(
            data=data,
            exchange=config["panoptes"]["rabbitmq"]["exchange"],
            queue=config["panoptes"]["rabbitmq"]["queue"],
            routing_key=config["panoptes"]["rabbitmq"]["routing_key"],
        )


        # Data structure
        data_dict = get_files_structure(config["data"]["data_folder"])
        if data_dict != {}:
            save_to_json(data=data_dict, filename=config["data"]["json_data_backup"])

        publish_to_rabbitmq(
            data=data_dict,
            exchange=config["data"]["rabbitmq"]["exchange"],
            queue=config["data"]["rabbitmq"]["queue"],
            routing_key=config["data"]["rabbitmq"]["routing_key"],
        )

        # Fetch every 30 seconds
        time.sleep(30)  
