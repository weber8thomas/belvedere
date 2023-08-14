import datetime
import os
from fastapi import FastAPI
import pika
import json
import uvicorn

app = FastAPI()

FILENAME = "latest_status.json"


def load_from_json():
    """Load the data from the JSON file."""
    try:
        with open("latest_status.json", "r") as file:
            data = json.load(file)
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        # If the file does not exist or there's an error in reading it,
        # return an empty dictionary or other default value
        return {}


def consume_last_message_from_rabbitmq():
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()

    # Fetch the message without auto acknowledgment
    method_frame, header_frame, body = channel.basic_get(
        queue="my_queue", auto_ack=False
    )
    print(method_frame, header_frame, body)

    if method_frame:
        # Extract the timestamp from the header frame
        if header_frame.timestamp:
            timestamp = header_frame.timestamp
            human_readable_timestamp = datetime.datetime.fromtimestamp(
                timestamp / 1000.0
            ).strftime("%Y-%m-%d %H:%M:%S")
            print(human_readable_timestamp)

        else:
            timestamp = None
        # Convert timestamp to human-readable format if necessary

        # # Acknowledge the message after processing
        # channel.basic_ack(delivery_tag=method_frame.delivery_tag)
        print("TOTOTO")
        connection.close()
        data = json.loads(body.decode("utf-8"))
        if data["workflows"] == [] and os.path.exists(FILENAME):
            print("RabbitMQ queue NOT empty but message is")
            print("Loading from JSON file...")
            data_json = load_from_json()
            file_timestamp = os.path.getmtime(FILENAME)
            file_timestamp = datetime.datetime.fromtimestamp(file_timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            print(data_json)
            return data_json, file_timestamp
        else:
            print("RabbitMQ queue NOT empty and message is NOT empty")
            return data, human_readable_timestamp

    else:
        if os.path.exists(FILENAME):
            connection.close()
            print("No message available, RabbitMQ queue is empty")
            print("Loading from JSON file...")
            data_json = load_from_json()
            file_timestamp = os.path.getmtime(FILENAME)
            file_timestamp = datetime.datetime.fromtimestamp(file_timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            print(data_json)
            return data_json, file_timestamp
        else:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return {"workflows": []}, current_time


@app.get("/get-progress")
def get_progress():
    data, timestamp = consume_last_message_from_rabbitmq()
    print(data, timestamp)
    return data, timestamp


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8059)
