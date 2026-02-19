import os
import time
import traceback
import paho.mqtt.client as mqtt

def create_mqtt_client(client_id="PI1",
                       host=None,
                       port=None,
                       keepalive=60,
                       max_retries=0,      # 0 = retry forever
                       retry_delay=2):
    host = host or os.getenv('MQTT_HOST') or os.getenv('MQTT_BROKER') or 'mosquitto'
    port = int(port or os.getenv('MQTT_PORT') or 1883)

    client = mqtt.Client(client_id=client_id)

    def on_connect(c, userdata, flags, rc):
        if rc == 0:
            print(f"[MQTT] Connected successfully as {client_id} -> {host}:{port}")
        else:
            print(f"[MQTT] Connection failed with code {rc} (client_id={client_id})")

    client.on_connect = on_connect

    attempt = 0
    while True:
        try:
            attempt += 1
            print(f"[MQTT] Trying to connect to {host}:{port} (attempt {attempt})")
            client.connect(host, port, keepalive)
            client.loop_start()
            time.sleep(0.1)
            return client
        except Exception as e:
            print(f"[MQTT] Connect attempt {attempt} failed: {e}")
            traceback.print_exc()
            if max_retries and attempt >= max_retries:
                print("[MQTT] Max retries reached, raising the last exception")
                raise
            print(f"[MQTT] Retrying in {retry_delay}s...")
            time.sleep(retry_delay)