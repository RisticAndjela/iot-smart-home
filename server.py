import json
from paho.mqtt import client as mqtt_client
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

influx_url = "http://localhost:8086" #192.168.107.170
influx_token = "iot-super-token"     
influx_org = "FTN"                   
influx_bucket = "iot-sensor-report"  

mqtt_broker = "localhost" #192.168.107.170
mqtt_topic = "sensors/#"

def write_to_influx(data):
    client = InfluxDBClient(url=influx_url, token=influx_token, org=influx_org)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    
    try:
        # Odredjujemo naziv merenja (Measurement)
        measurement_name = data.get("sensor_type", "SensorData").capitalize()
        if data.get("device") == "4SD": 
            measurement_name = "Kitchen_Timer"

        p = Point(measurement_name) \
            .tag("device", data.get("device", "unknown")) \
            .tag("pi", data.get("pi", "unknown")) \
            .tag("simulated", str(data.get("simulated", True))) \
            .tag("type", data.get("sensor_type", "generic")) \
            .field("value", float(data.get("value", 0.0)))
            
        write_api.write(bucket=influx_bucket, org=influx_org, record=p)
        print(f"Upisano u bazu: {data.get('device')} ({measurement_name}) = {data.get('value')}")
    except Exception as e:
        print(f"Greska pri upisu u Influx: {e}")

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT Broker!")
    client.subscribe("sensors/#")
    client.subscribe("actuators/#")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        
        # Tema: "sensors/pi1/ds1" ili "actuators/pi2/4sd"
        topic_parts = msg.topic.split('/')
        
        # 1. Pokusavamo da nadjemo ime uredjaja (zadnji deo teme)
        if "device" not in payload and len(topic_parts) >= 3:
            payload["device"] = topic_parts[2].upper() # npr. "DS1"
            
        # 2. Pokusavamo da nadjemo PI ID (srednji deo teme)
        if "pi" not in payload and len(topic_parts) >= 3:
            payload["pi"] = topic_parts[1] # npr. "pi1"
            
        write_to_influx(payload)
    except Exception as e:
        print(f"Greska pri obradi poruke: {e}")

if __name__ == "__main__":
    client = mqtt_client.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(mqtt_broker, 1883, 60)
    print("Bridge Server pokrenut i ceka podatke...")
    client.loop_forever()