import threading
import os
import sys
from settings import load_settings

current_dir = os.path.dirname(os.path.abspath(__file__))
simulation_dir = os.path.join(current_dir, 'simulation')
sys.path.append(simulation_dir)

def closing_main(stop_event, controller_thread, command_thread, threads):
    print("Stopping all threads... ")
    stop_event.set()
    controller_thread.join()
    command_thread.join()
    for t in threads:
        t.join()
    print("App stopped cleanly.")

# --- SIMULACIJA (FIX ZA WINDOWS) ---
try:
    import RPi.GPIO as GPIO
except ImportError:
    import fake_rpi
    sys.modules['RPi'] = fake_rpi.RPi
    sys.modules['RPi.GPIO'] = fake_rpi.RPi.GPIO
    import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)

from components.ds1 import run_ds
from components.uds1 import run_uds
from components.pir1 import run_pir
from actuators.dl1 import DoorLight
from actuators.db1 import DoorBuzzer
from actuators.controller import run_controller
from console.console import console_loop
from console.command_bus import command_loop

if __name__ == "__main__":
    print("Starting app")
    settings = load_settings()
    threads = []
    stop_event = threading.Event()
    
    try:
        if 'PI1' in settings:
            pi1_settings = settings['PI1']
            dl = None
            db = None
            
            # Pokretanje DS1 (Vrata)
            if 'DS1' in pi1_settings:
                run_ds(pi1_settings['DS1'], threads, stop_event)
            if 'DUS1' in pi1_settings:
                run_uds(pi1_settings['DUS1'], threads, stop_event)
            if 'DPIR1' in pi1_settings:
                run_pir(pi1_settings['DPIR1'], threads, stop_event)
            if 'DL' in pi1_settings:
                dl = DoorLight(pin=pi1_settings.get('DL', {}).get('pin', 17))
            if 'DB' in pi1_settings:
                db = DoorBuzzer(pin=pi1_settings.get('DB', {}).get('pin', 27))

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