import datetime
import pika
import time
import httpx
import json


def fetch_data_from_api():
    url_api = "http://127.0.0.1:8058/api/workflows"
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

        return {"workflows": []}
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
        return {"workflows": []}
        # return data


def publish_to_rabbitmq(data):
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()

    # Declare a topic exchange
    channel.exchange_declare(
        exchange="status_exchange", exchange_type="topic", durable=True
    )

    # Declare a queue named 'my_queue' with a message TTL of 300000 milliseconds (5 minutes)
    args = {"x-message-ttl": 30000}
    channel.queue_declare(queue="my_queue", durable=True, arguments=args)

    # Bind the queue to the exchange with the routing key 'latest_status'
    channel.queue_bind(
        exchange="status_exchange", queue="my_queue", routing_key="latest_status"
    )

    # Fetch the current timestamp
    current_timestamp = int(
        datetime.datetime.now().timestamp() * 1000
    )  # Current time in milliseconds
    print(current_timestamp)

    # Publish the message to the exchange with the 'latest_status' routing key
    channel.basic_publish(
        exchange="status_exchange",
        routing_key="latest_status",
        body=json.dumps(data),
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
            timestamp=current_timestamp,  # set timestamp
        ),
    )

    connection.close()


def save_to_json(data, filename="latest_status.json"):
    with open(filename, "w") as file:
        json.dump(data, file)

while True:
    data = fetch_data_from_api()
    print(data["workflows"], data["workflows"] == [])
    if data["workflows"] != []:
        save_to_json(data)
    publish_to_rabbitmq(data)
    time.sleep(30)  # Fetch every 30 seconds