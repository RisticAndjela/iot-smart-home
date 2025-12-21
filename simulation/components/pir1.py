import threading
import time
from simulators.pir1 import run_pir_simulator
from sensors.pir1 import run_pir_loop
from state.global_state import global_state

def pir_callback(motion_detected):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print("Sensor: DPIR1")
    if motion_detected:
        print("Status: MOTION DETECTED")
        global_state["motion"] = True
    else:
        print("Status: No motion")
        global_state["motion"] = False

def run_pir(settings, threads, stop_event):
    if settings['simulated']:
        print("Starting DPIR1 simulator")
        pir_thread = threading.Thread(target=run_pir_simulator, args=(3, pir_callback, stop_event))
        pir_thread.start()
        threads.append(pir_thread)
    else:
        print("Starting DPIR1 real loop")
        pir_thread = threading.Thread(target=run_pir_loop, args=(1, pir_callback, stop_event, settings))
        pir_thread.start()
        threads.append(pir_thread)