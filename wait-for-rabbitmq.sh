until $(curl --output /dev/null --silent --head --fail http://0.0.0.0:5672); do
    echo "Waiting for RabbitMQ..."
    sleep 5
done
