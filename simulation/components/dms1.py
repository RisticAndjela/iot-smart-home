import threading
import time
from sensors.dms1 import run_dms_loop
from simulators.dms1 import run_dms_simulator
from state.global_state import global_state

def dms_callback(val):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print("Sensor: Door Membrane Switch (DMS)")
    if val == 0:
        print("Status: RELEASED")
        global_state["dms_pressed"] = False
    else:
        print("Status: PRESSED")
        global_state["dms_pressed"] = True

def run_dms(settings, threads, stop_event):
    if settings.get('simulated', True):
        print("Starting DMS simulator")
        dms_thread = threading.Thread(target=run_dms_simulator, args=(0.5, dms_callback, stop_event))
        dms_thread.start()
        threads.append(dms_thread)
    else:
        print("Starting DMS real loop")
        dms_thread = threading.Thread(target=run_dms_loop, args=(0.2, dms_callback, stop_event, settings))
        dms_thread.start()
        threads.append(dms_thread)
