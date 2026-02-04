import time
import random

def run_btn_simulator(delay, callback, stop_event):
    while not stop_event.is_set():
        time.sleep(delay)
        # Simuliramo slučajan pritisak tastera
        value = random.randint(0, 1)
        callback(value)