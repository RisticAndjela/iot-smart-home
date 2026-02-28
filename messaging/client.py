import os
import time
import json
import paho.mqtt.client as mqtt


def _normalize_pi_topic(pi) -> str:
    if pi is None:
        return "piunknown"
    s = str(pi).strip().lower()
    if s.startswith("pi"):
        return s
    return f"pi{s}"

def create_mqtt_client(client_id="PI1", host=None, port=None, keepalive=60, max_retries=0, retry_delay=2, on_message_callback=None,):
    env_host = os.getenv("MQTT_HOST") or os.getenv("MQTT_BROKER")
    final_host = host or env_host or "localhost"  #192.168.107.170 
    final_port = int(port or os.getenv("MQTT_PORT") or 1883)

    client = mqtt.Client(client_id=str(client_id))

    def on_connect(c, userdata, flags, rc):
        if rc == 0:
            pi_topic = _normalize_pi_topic(client_id)  # typically "PI1"
            print(f"[MQTT] Connected as {client_id} -> {final_host}:{final_port}")
            c.subscribe(f"commands/{pi_topic}/#")
            print(f"[MQTT] Subscribed: commands/{pi_topic}/#")
            # subsribe to all sensors/actuators topics for now, since we want to capture all events for influxdb
            c.subscribe("sensors/#") 
            c.subscribe("actuators/#")
            print("[MQTT] Subscribed: sensors/#, actuators/#")
        else:
            print(f"[MQTT] Connection F A I L E D, rc={rc}") 

    def internal_on_message(c, userdata, msg):
        payload = msg.payload.decode(errors="replace")
        # print(f"[MQTT] Received on {msg.topic}: {payload}")
        if on_message_callback:
            on_message_callback(c, userdata, msg)

    client.on_connect = on_connect
    client.on_message = internal_on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30) # ww dont need to think about reconnection, paho handles it

    attempt = 0
    while True: # this will happen hopefully only once at startup, since paho will handle reconnections after that
        try:
            attempt += 1
            print(f"[MQTT] Connecting to {final_host}:{final_port} (attempt {attempt})")
            client.connect(final_host, final_port, keepalive)
            client.loop_start()
            time.sleep(0.3)
            return client
        except Exception as e:
            print(f"[MQTT] Connect attempt {attempt} failed: {e}")
            if max_retries and attempt >= max_retries:
                raise
            time.sleep(retry_delay)