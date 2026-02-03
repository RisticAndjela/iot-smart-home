import paho.mqtt.client as mqtt
import time
import json

def create_mqtt_client(client_id="PI1"):
    client = mqtt.Client(client_id=client_id)
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"[MQTT] Connected successfully as {client_id}")
        else:
            print(f"[MQTT] Connection failed with code {rc}")

    client.on_connect = on_connect

    client.connect("host.docker.internal", 1883)
    client.loop_start()  # start the network loop in background

    return client