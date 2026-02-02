import paho.mqtt.client as mqtt

def create_mqtt_client():
    client = mqtt.Client(client_id="PI1")
    client.connect("localhost", 1883)
    return client
