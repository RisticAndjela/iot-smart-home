import threading
import time
from simulators.ds1 import run_ds_simulator
from sensors.ds1 import run_ds_loop
from state.global_state import global_state

def ds_callback(val):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print("Sensor: Door Sensor (DS1)")
    if val == 0:
        print("Status: Door CLOSED")
        global_state["door_open"] = False
    else:
        print("Status: Door OPEN")
        global_state["door_open"] = True

def run_ds(settings, threads, stop_event):
    if settings['simulated']:
        print("Starting DS1 simulator")
        ds_thread = threading.Thread(target=run_ds_simulator, args=(2, ds_callback, stop_event))
        ds_thread.start()
        threads.append(ds_thread)
    else:
        print("Starting DS1 real loop")
        ds_thread = threading.Thread(target=run_ds_loop, args=(0.5, ds_callback, stop_event, settings))
        ds_thread.start()
        threads.append(ds_thread)