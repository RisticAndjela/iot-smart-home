import os
import time
import json  
import traceback
import paho.mqtt.client as mqtt

def create_mqtt_client(client_id="PI1",
                       host=None,
                       port=None,
                       keepalive=60,
                       max_retries=0,
                       retry_delay=2,
                       on_message_callback=None): 
    
    env_host = os.getenv('MQTT_HOST') or os.getenv('MQTT_BROKER')
    if host:
        final_host = host
    elif env_host:
        final_host = env_host
    else:
        final_host = 'localhost' #192.168.107.170 

    final_port = int(port or os.getenv('MQTT_PORT') or 1883)
    client = mqtt.Client(client_id=client_id)

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"[MQTT] Connected successfully as {client_id} -> {final_host}:{final_port}")
            c.subscribe(f"commands/{client_id.lower()}/#")
        else:
            print(f"[MQTT] Connection failed with code {rc}")

    def internal_on_message(c, userdata, msg):
        print(f"[MQTT] Received message on {msg.topic}: {msg.payload.decode()}")
        if on_message_callback:
            on_message_callback(c, userdata, msg)

    client.on_connect = on_connect
    client.on_message = internal_on_message

    attempt = 0
    while True:
        try:
            attempt += 1
            print(f"[MQTT] Trying to connect to {final_host}:{final_port} (attempt {attempt})")
            client.connect(final_host, final_port, keepalive)
            client.loop_start()
            time.sleep(0.5) 
            return client
        except Exception as e:
            print(f"[MQTT] Connect attempt {attempt} failed: {e}")
            if max_retries and attempt >= max_retries:
                raise
            time.sleep(retry_delay)