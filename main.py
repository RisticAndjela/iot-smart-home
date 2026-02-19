import threading
import os
import sys
import time

from messaging.batch_publisher import batch_publisher
from messaging.client import create_mqtt_client
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

# --- Import komponenti ---
from simulation.components.ds import run_ds
from simulation.components.uds import run_uds
from simulation.components.pir import run_pir
from simulation.components.dms import run_dms
from simulation.components.dht import run_dht
from simulation.components.gyro import run_gyro
from simulation.components.btn import run_btn 
from simulation.actuators.display import run_4sd

from simulation.actuators.dl1 import DoorLight
from simulation.actuators.db1 import DoorBuzzer
from simulation.actuators.controller import run_controller
from simulation.console.console import console_loop
from simulation.console.command_bus import command_loop

def closing_main(stop_event, controller_thread, command_thread, threads):
    print("Stopping all threads... ")
    stop_event.set()
    if controller_thread: controller_thread.join()
    if command_thread: command_thread.join()
    for t in threads: t.join()
    print("App stopped cleanly.")

if __name__ == "__main__":
    print("Starting app")
    settings = load_settings()
    threads = []
    stop_event = threading.Event()

    try:
        mqtt_client = create_mqtt_client()
        publisher_thread = threading.Thread(
            target=batch_publisher,
            args=(mqtt_client, stop_event),
            daemon=True
        )
        publisher_thread.start()
    except Exception as e:
        print(f"MQTT Error: {e}")

    controller_thread = None
    command_thread = None
    dl = None
    db = None

    try:
        for pi_id in settings:
            pi_settings = settings[pi_id]
            sensors = pi_settings.get("sensors", {})
            actuators = pi_settings.get("actuators", {})

            # --- SENZORI PI 1 ---
            if pi_id == "PI1":
                if 'DS1' in sensors: run_ds(sensors['DS1'], threads, stop_event)
                if 'DUS1' in sensors: run_uds(sensors['DUS1'], threads, stop_event)
                if 'DPIR1' in sensors: run_pir(sensors['DPIR1'], threads, stop_event)
                if 'DMS1' in sensors: run_dms(sensors['DMS1'], threads, stop_event)

            # --- SENZORI PI 2 ---
            if pi_id == "PI2":
                if 'DS2' in sensors: run_ds(sensors['DS2'], threads, stop_event)
                if 'DUS2' in sensors: run_uds(sensors['DUS2'], threads, stop_event)
                if 'DPIR2' in sensors: run_pir(sensors['DPIR2'], threads, stop_event)
                if 'BTN' in sensors: run_btn(sensors['BTN'], threads, stop_event)
                if 'DHT3' in sensors: run_dht(sensors['DHT3'], threads, stop_event)
                if 'GSG' in sensors: run_gyro(sensors['GSG'], threads, stop_event)
            # --- SENZORI PI 3 ---
            if pi_id == "PI3":
                if "DHT1" in sensors: run_dht(sensors['DHT1'], threads, stop_event)
                if "DHT2" in sensors: run_dht(sensors['DHT2'], threads, stop_event)
                if "IR" in sensors: run_uds(sensors['IR'], threads, stop_event)
                if "DPIR3" in sensors: run_pir(sensors['DPIR3'], threads, stop_event)
            # --- AKTUATORI ---
            if 'DL' in actuators:
                dl = DoorLight(pin=actuators['DL']['pin'])
            if 'DB' in actuators:
                db = DoorBuzzer(pin=actuators['DB']['pin'])
            if pi_id == "PI3" and 'BRGB' in actuators:
                print(f"Running BRGB for PI {pi_id}")
            if pi_id == "PI3" and 'LCD' in actuators:
                print(f"Running LCD for PI {pi_id}")
            if pi_id == "PI2" and '4SD' in actuators:
                run_4sd(actuators['4SD'], threads, stop_event)

        if dl and db:
            controller_thread = run_controller(dl, db, stop_event)
        
        command_thread = threading.Thread(target=command_loop, args=(stop_event,), daemon=True)
        command_thread.start()

        console_loop(stop_event)

    except KeyboardInterrupt:
        print("KeyboardInterrupt detected.")
    finally:
        closing_main(stop_event, controller_thread, command_thread, threads)