import threading
import time
import random

from messaging.event_queue import event_queue
from simulation.sensors.sensor_event import SensorEvent
from simulation.state.global_state import global_state


def run_dht(settings, threads, stop_event):
    device_name = settings["device"]  # "DHT1", "DHT2", "DHT3"
    pi_id = settings["pi"]
    simulated = settings.get("simulated", True)
    pin = settings.get("pin", 17)
    d_id = device_name.lower()

    def emit(measurement_type: str, value: float):
        event = SensorEvent(
            pi_id=str(pi_id),
            device=str(device_name).upper(),
            kind="sensor",
            type=measurement_type,          # "temperature" / "humidity"
            sensor_type=measurement_type,   # legacy alias
            value=float(value),
            simulated=bool(simulated),
            timestamp=time.time(),
        )
        event_queue.put(event)

    def process_data(temp, hum):
        global_state[f"{d_id}_temp"] = temp
        global_state[f"{d_id}_hum"] = hum

        print(f"[{device_name}] Temp: {temp}°C, Hum: {hum}%")

        emit("temperature", temp)
        emit("humidity", hum)

    def dht_sim_loop():
        while not stop_event.is_set():
            temp = round(random.uniform(20.0, 30.0), 1)
            hum = round(random.uniform(40.0, 60.0), 1)
            process_data(temp, hum)
            time.sleep(5)

    def dht_real_loop():
        from simulation.sensors.LA_DHT import DHT
        dht_sensor = DHT(pin)

        while not stop_event.is_set():
            chk = dht_sensor.readDHT11()
            if chk == dht_sensor.DHTLIB_OK:
                process_data(dht_sensor.temperature, dht_sensor.humidity)
            else:
                print(f"[ERROR] {device_name} Error code: {chk}")
            time.sleep(5)

    target = dht_sim_loop if simulated else dht_real_loop
    t = threading.Thread(target=target, name=f"Thread-{device_name}", daemon=True)
    t.start()
    threads.append(t)