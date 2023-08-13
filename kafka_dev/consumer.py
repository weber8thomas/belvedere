from kafka import KafkaConsumer
import json

consumer = KafkaConsumer('api_data_topic',
                         bootstrap_servers='localhost:9092',
                         value_deserializer=lambda m: json.loads(m.decode('utf-8')))

for message in consumer:
    data = message.value
    # Handle or process the data here
    print(data)
