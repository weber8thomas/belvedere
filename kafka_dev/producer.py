from kafka import KafkaProducer
import requests
import json

producer = KafkaProducer(bootstrap_servers='localhost:9092',
                         value_serializer=lambda v: json.dumps(v).encode('utf-8'))

url_api = "http://127.0.0.1:8058/api/workflows"

response = requests.get(url_api)
data = response.json()

producer.send('api_data_topic', data)
producer.flush()
