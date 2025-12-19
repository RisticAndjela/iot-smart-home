import threading
import time
from simulators.uds1 import run_uds_simulator
from sensors.uds1 import run_uds_loop

def uds_callback(distance):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Sensor: DUS1")
    print(f"Distance: {distance} cm")

def run_uds(settings, threads, stop_event):
    if settings['simulated']:
        print("Starting DUS1 simulator")
        uds_thread = threading.Thread(target=run_uds_simulator, args=(2, uds_callback, stop_event))
        uds_thread.start()
        threads.append(uds_thread)
    else:
        print("Starting DUS1 real loop")
        uds_thread = threading.Thread(target=run_uds_loop, args=(2, uds_callback, stop_event, settings))
        uds_thread.start()
        threads.append(uds_thread)