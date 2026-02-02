import threading
import os
import sys
import time

from messaging import batch_publisher
from messaging.client import create_mqtt_client
from settings import load_settings

# --- SIMULACIJA (FIX ZA WINDOWS) ---
try:
    import RPi.GPIO as GPIO
except ImportError:
    import fake_rpi
    sys.modules['RPi'] = fake_rpi.RPi
    sys.modules['RPi.GPIO'] = fake_rpi.RPi.GPIO
    import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)

# --- Import komponenti ---
from components.ds import run_ds
from components.uds import run_uds
from components.pir import run_pir
from components.dms import run_dms
from simulation.actuators.dl1 import DoorLight
from simulation.actuators.db1 import DoorBuzzer
from simulation.actuators.controller import run_controller
from simulation.console.console import console_loop
from simulation.console.command_bus import command_loop

def closing_main(stop_event, controller_thread, command_thread, threads):
    print("Stopping all threads... ")
    stop_event.set()
    controller_thread.join()
    command_thread.join()
    for t in threads:
        t.join()
    print("App stopped cleanly.")

if __name__ == "__main__":
    print("Starting app")
    settings = load_settings()
    threads = []
    stop_event = threading.Event()

    # --- MQTT ---
    mqtt_client = create_mqtt_client()
    publisher_thread = threading.Thread(
        target=batch_publisher,
        args=(mqtt_client, stop_event),
        daemon=True
    )
    publisher_thread.start()

    try:
        # --- Pokretanje senzora i aktuatora za oba PI-a ---
        for pi_id in settings:
            pi_settings = settings[pi_id]

            sensors = pi_settings.get("sensors", {})
            actuators = pi_settings.get("actuators", {})

            # Door Sensor
            if 'DS1' in sensors and pi_id == "PI1":
                run_ds(sensors['DS1'], threads, stop_event)
            if 'DS2' in sensors and pi_id == "PI2":
                run_ds(sensors['DS2'], threads, stop_event)

            # Ultrasonic
            if 'DUS1' in sensors and pi_id == "PI1":
                run_uds(sensors['DUS1'], threads, stop_event)
            if 'DUS2' in sensors and pi_id == "PI2":
                run_uds(sensors['DUS2'], threads, stop_event)

            # Motion PIR
            if 'DPIR1' in sensors and pi_id == "PI1":
                run_pir(sensors['DPIR1'], threads, stop_event)
            if 'DPIR2' in sensors and pi_id == "PI2":
                run_pir(sensors['DPIR2'], threads, stop_event)

            # Membrane Switch
            if 'DMS1' in sensors and pi_id == "PI1":
                run_dms(sensors['DMS1'], threads, stop_event)
            if 'DMS2' in sensors and pi_id == "PI2":
                run_dms(sensors['DMS2'], threads, stop_event)

            # Aktuatori
            dl = None
            db = None
            if 'DL' in actuators:
                dl = DoorLight(pin=actuators['DL']['pin'])
            if 'DB' in actuators:
                db = DoorBuzzer(pin=actuators['DB']['pin'])

        # --- CONTROLLER ---
        controller_thread = run_controller(dl, db, stop_event)

        # --- COMMAND BUS THREAD ---
        command_thread = threading.Thread(target=command_loop, args=(stop_event,), daemon=True)
        command_thread.start()

        # --- CONSOLE DISPLAY ---
        console_loop(stop_event)

    except KeyboardInterrupt:
        print("KeyboardInterrupt detected. Stopping app...")
        
    finally:
        closing_main(stop_event, controller_thread, command_thread, threads)
