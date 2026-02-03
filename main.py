import threading
import sys
import time

from messaging.batch_publisher import batch_publisher
from messaging.client import create_mqtt_client
from database.sensor_service import write_event_to_influx
from settings import load_settings

# --- SIMULACIJA ---
try:
    import RPi.GPIO as GPIO
except ImportError:
    import fake_rpi
    sys.modules['RPi'] = fake_rpi.RPi
    sys.modules['RPi.GPIO'] = fake_rpi.RPi.GPIO
    import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)


# --- InfluxDB ---
from influxdb_client import InfluxDBClient, WriteOptions
from database.sensor_service import write_event_to_influx

INFLUX_URL = "http://localhost:8086"  
INFLUX_TOKEN = "f8CPYZfj0gcuuUouK-DzX5Egu1CxM4-XQBpGcEbHijvxqGMvSipf2GGAXDBHg_jSAQ7TI1HVWw-TH1BTl4-RBQ=="
INFLUX_ORG = "FTN"
INFLUX_BUCKET = "iot-sensor-report"

try:
    influx_client = InfluxDBClient(
        url=INFLUX_URL,
        token=INFLUX_TOKEN,
        org=INFLUX_ORG
    )
    write_api = influx_client.write_api(
        write_options=WriteOptions(batch_size=10, flush_interval=1000)
    )
    print("InfluxDB connected")
except Exception as e:
    print("InfluxDB NOT available:", e)
    write_api = None

# --- Import komponenti ---
from simulation.components.ds import run_ds
from simulation.components.uds import run_uds
from simulation.components.pir import run_pir
from simulation.components.dms import run_dms
from simulation.components.dht import run_dht
from simulation.components.btn import run_btn
from simulation.components.gyro import run_gyro

from simulation.actuators.display import run_4sd
from simulation.actuators.dl1 import DoorLight
from simulation.actuators.db1 import DoorBuzzer
from simulation.actuators.controller import run_controller
from simulation.console.console import console_loop
from simulation.console.command_bus import command_loop


def closing_main(stop_event, controller_thread, command_thread, threads):
    print("Stopping all threads...")
    stop_event.set()

    if controller_thread:
        controller_thread.join()
    if command_thread:
        command_thread.join()

    for t in threads:
        t.join()

    if write_api:
        write_api.flush()
    if influx_client:
        influx_client.close()

    print("App stopped cleanly.")


if __name__ == "__main__":
    print("Starting app")
    settings = load_settings()
    threads = []
    stop_event = threading.Event()

    # --- MQTT ---
    try:
        mqtt_client = create_mqtt_client()
        print("MQTT connected")
    except Exception as e:
        print("MQTT NOT available:", e)
        mqtt_client = None

    # --- Publisher (MQTT + DB) ---
    publisher_thread = threading.Thread(
        target=batch_publisher,
        args=(mqtt_client, stop_event),
        kwargs={
            "write_callback": lambda event: write_event_to_influx(write_api, INFLUX_BUCKET, event)
        },
        daemon=True
    )

    publisher_thread.start()

    controller_thread = None
    command_thread = None
    dl = None
    db = None

    try:
        for pi_id in settings:
            pi_settings = settings[pi_id]
            sensors = pi_settings.get("sensors", {})
            actuators = pi_settings.get("actuators", {})

            # --- SENZORI ---

            # Door Sensor (DS1 i DS2)
            if 'DS1' in sensors and pi_id == "PI1":
                run_ds(sensors['DS1'], threads, stop_event)
            if 'DS2' in sensors and pi_id == "PI2":
                run_ds(sensors['DS2'], threads, stop_event)

            # Ultrasonic (DUS1 i DUS2)
            if 'DUS1' in sensors and pi_id == "PI1":
                run_uds(sensors['DUS1'], threads, stop_event)
            if 'DUS2' in sensors and pi_id == "PI2":
                run_uds(sensors['DUS2'], threads, stop_event)

            # Motion PIR (DPIR1 i DPIR2)
            if 'DPIR1' in sensors and pi_id == "PI1":
                run_pir(sensors['DPIR1'], threads, stop_event)
            if 'DPIR2' in sensors and pi_id == "PI2":
                run_pir(sensors['DPIR2'], threads, stop_event)

            # Membrane Switch (DMS1)
            if 'DMS1' in sensors and pi_id == "PI1":
                run_dms(sensors['DMS1'], threads, stop_event)
            
            # --- SENZORI ZA PI 2 ---
            
            # Kitchen Button (BTN) - Koristimo run_ds jer je isto (taster)
            if 'BTN' in sensors and pi_id == "PI2":
                run_ds(sensors['BTN'], threads, stop_event)

            # Kitchen DHT (DHT3)
            if 'DHT3' in sensors and pi_id == "PI2":
                run_dht(sensors['DHT3'], threads, stop_event)

            # Gyroscope (GSG)
            if 'GSG' in sensors and pi_id == "PI2":
                run_gyro(sensors['GSG'], threads, stop_event)
            if pi_id == "PI1":
                if 'DS1' in sensors: run_ds(sensors['DS1'], threads, stop_event, write_callback=lambda event: write_event_to_influx(write_api, INFLUX_BUCKET, event))
                if 'DUS1' in sensors: run_uds(sensors['DUS1'], threads, stop_event, write_callback=lambda event: write_event_to_influx(write_api, INFLUX_BUCKET, event))
                if 'DPIR1' in sensors: run_pir(sensors['DPIR1'], threads, stop_event, write_callback=lambda event: write_event_to_influx(write_api, INFLUX_BUCKET, event))
                if 'DMS1' in sensors: run_dms(sensors['DMS1'], threads, stop_event, write_callback=lambda event: write_event_to_influx(write_api, INFLUX_BUCKET, event))

            if pi_id == "PI2":
                if 'DS2' in sensors: run_ds(sensors['DS2'], threads, stop_event, write_callback=lambda event: write_event_to_influx(write_api, INFLUX_BUCKET, event))
                if 'DUS2' in sensors: run_uds(sensors['DUS2'], threads, stop_event, write_callback=lambda event: write_event_to_influx(write_api, INFLUX_BUCKET, event))
                if 'DPIR2' in sensors: run_pir(sensors['DPIR2'], threads, stop_event, write_callback=lambda event: write_event_to_influx(write_api, INFLUX_BUCKET, event))
                if 'BTN' in sensors: run_ds(sensors['BTN'], threads, stop_event, write_callback=lambda event: write_event_to_influx(write_api, INFLUX_BUCKET, event))
                if 'DHT3' in sensors: run_dht(sensors['DHT3'], threads, stop_event)
                if 'GSG' in sensors: run_gyro(sensors['GSG'], threads, stop_event)

            # Kitchen Button (BTN)
            if 'BTN' in sensors and pi_id == "PI2":
                run_btn(sensors['BTN'], threads, stop_event)

            # --- AKTUATORI ---
            if 'DL' in actuators:
                dl = DoorLight(pin=actuators['DL']['pin'])
            if 'DB' in actuators:
                db = DoorBuzzer(pin=actuators['DB']['pin'])

            if pi_id == "PI2" and '4SD' in actuators:
                run_4sd(actuators['4SD'], threads, stop_event)

        # --- CONTROLLER ---
        if dl and db:
            controller_thread = run_controller(dl, db, stop_event)
        else:
            print("Controller not started (DL/DB missing)")

        # --- COMMAND BUS ---
        command_thread = threading.Thread(
            target=command_loop,
            args=(stop_event,),
            daemon=True
        )
        command_thread.start()

        # --- CONSOLE ---
        console_loop(stop_event)

    except KeyboardInterrupt:
        print("KeyboardInterrupt detected")

    finally:
        closing_main(stop_event, controller_thread, command_thread, threads)
