import threading
import time
import os
import sys
from settings import load_settings

current_dir = os.path.dirname(os.path.abspath(__file__))
simulation_dir = os.path.join(current_dir, 'simulation')
sys.path.append(simulation_dir)

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

if __name__ == "__main__":
    print('Starting app')
    settings = load_settings()
    threads = []
    stop_event = threading.Event()
    
    try:
        # --- ZA PI 1 ---
        if 'PI1' in settings:
            pi1_settings = settings['PI1']
            
            # Pokretanje DS1 (Vrata)
            if 'DS1' in pi1_settings:
                run_ds(pi1_settings['DS1'], threads, stop_event)
                
            # Pokretanje DUS1 (Ultrazvuk)
            if 'DUS1' in pi1_settings:
                run_uds(pi1_settings['DUS1'], threads, stop_event)
                
            # Pokretanje DPIR1 (Pokret)
            if 'DPIR1' in pi1_settings:
                run_pir(pi1_settings['DPIR1'], threads, stop_event)
        # ------------------------

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print('Stopping app')
        stop_event.set()
        for t in threads:
            t.join()